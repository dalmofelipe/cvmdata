"""
Classificação de empresas CVM a ter indicadores calculados.

O universo de empresas classificado é a união das tabelas ``*_clean`` — quem de
fato reportaram demonstrativos. O perfil de contas aplicado em cada uma delas, 
vem das regras estrutural em :mod:`cvmdata.transform.profile.rules`.

Todo processo é realizado na data base DuckDB, e o resultado é persistido na 
tabela ``company_classification``

Referências: docs/profiles.md, docs/classificacao.md
"""

from __future__ import annotations

import logging

import duckdb

from cvmdata.ingestion.tables import (
    CLEAN_TABLES,
    TB_CAD_CIA_ABERTA_RAW,
    TB_COMPANY_CLASSIFICATION,
)
from cvmdata.transform.info_cad import sql
from cvmdata.transform.info_cad.models import (
    ClassificationCounts,
    MissingCadCiaAbertaTableError,
    MissingCleanTablesError,
)
from cvmdata.transform.profile import repository as profile_repository
from cvmdata.transform.profile.rules import STRUCTURAL_RULES
from cvmdata.utils.database import existing_tables, replace_table_contents

logger = logging.getLogger(__name__)


def _require_tables(conn: duckdb.DuckDBPyConnection) -> None:
    tables = existing_tables(conn)

    missing_clean = [t for t in CLEAN_TABLES if t not in tables]
    if missing_clean:
        raise MissingCleanTablesError(
            f"Tabelas clean faltando ({', '.join(missing_clean)}) — "
            "rode 'normalize' antes de classificar"
        )

    if TB_CAD_CIA_ABERTA_RAW not in tables:
        raise MissingCadCiaAbertaTableError(
            f"{TB_CAD_CIA_ABERTA_RAW} não existe — rode 'load_info_cad' antes de "
            "classificar (sem ela o perfil sai certo, mas CNPJ e nome de empresa "
            "perdem o vínculo com o cadastro)"
        )


def classify_info_cad(conn: duckdb.DuckDBPyConnection) -> ClassificationCounts:
    """Classifica o universo de empresas com demonstrativos reportados."""
    
    _require_tables(conn)

    params: list[object] = []
    rule_matches_sql = sql.rule_matches_sql(STRUCTURAL_RULES, params)
    profile_sql, rule_applied_sql = sql.classification_sql(STRUCTURAL_RULES)

    statement = sql.SQL_CLASSIFY.format(
        rule_matches_sql=rule_matches_sql,
        profile_sql=profile_sql,
        rule_applied_sql=rule_applied_sql,
    )

    replace_table_contents(conn, TB_COMPANY_CLASSIFICATION, statement, params)
    by_profile, by_rule = profile_repository.count_by_profile_and_rule(conn)

    total = sum(by_profile.values())
    logger.info(
        "Classificados (universo=%d, %s)",
        total,
        ", ".join(f"{p}={n}" for p, n in sorted(by_profile.items())),
    )
    logger.debug("Classificação por regra: %s", by_rule)

    return {"total": total, "by_profile": by_profile, "by_rule": by_rule}
