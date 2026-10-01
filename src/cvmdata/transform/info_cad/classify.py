"""Classificação de empresas CVM por layout contábil.

O universo classificado é a união das tabelas ``*_clean`` — as empresas que de
fato reportaram demonstrativos. O cadastro é dado **descritivo**: entra por
``LEFT JOIN`` e nunca decide o perfil (ver :mod:`cvmdata.transform.profile`).

Fluxo:

1. Universo = ``UNION`` das clean existentes. Sem nenhuma clean não há o que
   classificar, e a função levanta erro.
2. ``cad_cia_aberta_raw`` entra uma linha por CNPJ, a mais recente por
   ``DT_INI_SIT``. **Sem filtro de ``SIT``**: empresa com ``SIT != 'ATIVO'`` e
   com demonstrativo é classificada normalmente. Seis bancos do universo estão
   exatamente nesse caso — todos com layout financeiro e todos descartados pelo
   filtro anterior.
3. Empresa ausente do cadastro recebe ``cd_cvm`` e ``denom_social`` das clean.
   ``denom_comerc`` não é fabricado: viria vazio e ensinaria mal o
   ``scripts/indicators.py``, que resolve ticker por ele.
4. Um statement set-based reconstrói a tabela inteira
   (:func:`cvmdata.transform.profile.repository.rebuild`). A reconstrução — e não
   um ``INSERT OR REPLACE`` — é o que garante que a classificação não carrega
   linha obsoleta: um CNPJ que saiu do universo no ano corrente precisa sumir.

Este módulo é só a orquestração: as strings estão em
:mod:`cvmdata.transform.info_cad.queries`, as fontes em
:mod:`cvmdata.transform.info_cad.repository` e a reconstrução em
:mod:`cvmdata.transform.profile.repository`.
"""

from __future__ import annotations

import logging

import duckdb

from cvmdata.ingestion.tables import (
    TB_CAD_CIA_ABERTA_RAW,
    TB_COMPANY_CLASSIFICATION,
    TB_SETOR_PROFILE_MAP,
)
from cvmdata.transform.info_cad import queries
from cvmdata.transform.info_cad.models import ClassificationCounts
from cvmdata.transform.info_cad.repository import require_clean_tables
from cvmdata.transform.profile import repository as profile_repo
from cvmdata.transform.profile.rules import SIGNATURE_RULES
from cvmdata.transform.profile.sql import classification_sql, signature_flags_sql

logger = logging.getLogger(__name__)


def classify_info_cad(conn: duckdb.DuckDBPyConnection) -> ClassificationCounts:
    """Classifica o universo de empresas com demonstrativos.

    Reconstrói ``company_classification`` inteira em uma transação: a tabela é
    derivada do universo, e um ``INSERT OR REPLACE`` deixaria para trás o CNPJ
    que deixou de aparecer nas clean.

    Returns:
        ``{'total': int, 'by_profile': {...}, 'by_rule': {...}}``.
        ``steps.py`` usa ``total`` para decidir success/warning.

    Raises:
        MissingCleanTablesError: Se alguma das três ``*_clean`` não existir. Um
            universo incompleto não classifica: o perfil cairia no ``default``
            por falta de dado, não por layout padrão.
    """
    tables = profile_repo.existing_tables(conn)
    clean = require_clean_tables(conn)

    has_cadastro = TB_CAD_CIA_ABERTA_RAW in tables
    has_overrides = TB_SETOR_PROFILE_MAP in tables
    if not has_cadastro:
        logger.warning(
            "%s ausente — classificando sem dados cadastrais (perfil só por assinatura)",
            TB_CAD_CIA_ABERTA_RAW,
        )

    params: list[object] = []
    signature_flags, flag_aliases = signature_flags_sql(
        SIGNATURE_RULES, cnpj_expr="u.CNPJ_CIA", params=params
    )
    profile_sql, rule_applied_sql = classification_sql(
        SIGNATURE_RULES,
        signature_exprs=[f"s.{alias}" for alias in flag_aliases],
        setor_expr="c.setor_ativ",
        in_cadastro_expr="c.CNPJ_CIA",
        override_expr="spm.profile_id" if has_overrides else "NULL",
    )

    sql = queries.SQL_CLASSIFY.format(
        universe=queries.universe_sql(clean),
        universe_descriptors=queries.descriptors_sql(clean),
        signature_flags=signature_flags,
        cad_source=(
            queries.SQL_CAD.format(cad_table=TB_CAD_CIA_ABERTA_RAW)
            if has_cadastro
            else queries.SQL_CAD_EMPTY
        ),
        classification=TB_COMPANY_CLASSIFICATION,
        profile_sql=profile_sql,
        rule_applied_sql=rule_applied_sql,
        override_join=queries.override_join(TB_SETOR_PROFILE_MAP if has_overrides else None),
    )

    profile_repo.rebuild(conn, sql, params)
    by_profile, by_rule = profile_repo.count_by_profile_and_rule(conn)

    total = sum(by_profile.values())
    logger.info(
        "Classificação: %d empresas do universo — por perfil %s",
        total,
        ", ".join(f"{p}={n}" for p, n in sorted(by_profile.items())),
    )
    logger.debug("Classificação por regra: %s", by_rule)

    return {"total": total, "by_profile": by_profile, "by_rule": by_rule}