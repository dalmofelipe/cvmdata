"""
SQL da classificação cadastral.

SQL_CLASSIFY é composta por três partes:

1. CTE rule_matches: avalia todas as regras estruturais e gera uma flag booleana por regra.
2. SELECT principal: junta o universo de empresas com a tabela de cadastro e as flags de 
regras, e gera profile_id e rule_applied.
3. INSERT INTO: insere o resultado na tabela de classificação: company_classification.

Referências: docs/profiles.md, docs/classificacao.md
"""

from __future__ import annotations

from cvmdata.ingestion.tables import (
    TB_BPA_CLEAN,
    TB_BPP_CLEAN,
    TB_CAD_CIA_ABERTA_RAW,
    TB_COMPANY_CLASSIFICATION,
    TB_DRE_CLEAN,
)
from cvmdata.transform.profile.models import StructuralRule
from cvmdata.transform.profile.rules import FALLBACK_PROFILE
from cvmdata.utils.text import NORM_DS_CONTA_SQL

SQL_CLASSIFY = f"""
WITH universo AS (
    SELECT
        CNPJ_CIA,
        first(CD_CVM    ORDER BY DT_REFER DESC NULLS LAST, CD_CVM    ASC NULLS LAST) AS cd_cvm,
        first(DENOM_CIA ORDER BY DT_REFER DESC NULLS LAST, DENOM_CIA ASC NULLS LAST) AS denom_social
    FROM (
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_BPA_CLEAN}
            UNION
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_BPP_CLEAN}
            UNION
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_DRE_CLEAN}
    )
    GROUP BY CNPJ_CIA
),
cad AS (
    SELECT
        CNPJ_CIA,
        CD_CVM,
        DENOM_SOCIAL,
        DENOM_COMERC,
        NULLIF(trim(CAST(SETOR_ATIV AS VARCHAR)), '') AS setor_ativ,
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA
            ORDER BY
                TRY_CAST(DT_INI_SIT AS DATE) DESC NULLS LAST,
                CD_CVM ASC NULLS LAST,
                DENOM_SOCIAL ASC NULLS LAST
        ) AS rn
    FROM {TB_CAD_CIA_ABERTA_RAW}
),
rule_matches AS (
    SELECT
        u.CNPJ_CIA AS cnpj_cia,
        {{rule_matches_sql}}
    FROM universo u
)
INSERT INTO {TB_COMPANY_CLASSIFICATION}
    (cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ,
     profile_id, rule_applied, updated_at)
SELECT
    u.CNPJ_CIA                        AS cnpj_cia,
    COALESCE(CAST(c.CD_CVM AS VARCHAR), CAST(u.cd_cvm AS VARCHAR)) AS cd_cvm,
    COALESCE(c.DENOM_SOCIAL, u.denom_social) AS denom_social,
    c.DENOM_COMERC                    AS denom_comerc,
    c.setor_ativ                      AS setor_ativ,
    {{profile_sql}}                   AS profile_id,
    {{rule_applied_sql}}              AS rule_applied,
    current_timestamp                 AS updated_at
FROM universo u
LEFT JOIN cad c
    ON c.CNPJ_CIA = u.CNPJ_CIA
    AND c.rn = 1
LEFT JOIN rule_matches rm
    ON rm.cnpj_cia = u.CNPJ_CIA
"""


def _sql_str(value: str) -> str:
    """Literal SQL entre aspas simples, com escape."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def rule_match_alias(index: int) -> str:
    """Nome da coluna booleana da regra ``index`` na CTE de flags."""
    return f"rule_{index}_match"


def rule_conditions_sql(
    rule: StructuralRule,
    params: list[object],
) -> str:
    """Renderiza cada condição de uma regra e as combina com ``AND``.

    Cada condição de uma regra estrutural vira um ``EXISTS`` correlacionado pelo CNPJ.
    O resultado só é verdadeiro quando todos os ``EXISTS`` encontram correspondência.
    Os parâmetros são anexados a ``params`` na mesma ordem dos placeholders.

    ### Args
        rule: Regra a renderizar.
        params: A lista de parâmetros acumulados é mutada in place.

    ### Returns
        Predicado SQL booleano, ou string vazia se a regra não tiver condições.

    Referências: docs/profiles.md, docs/classificacao.md
    """
    clauses: list[str] = []
    for index, condition in enumerate(rule.conditions):
        alias = f"condition_{index}"
        clauses.append(
            f"EXISTS ("
            f"  SELECT 1 FROM {condition.clean_table} {alias}"
            f"  WHERE {alias}.CNPJ_CIA = u.CNPJ_CIA"
            f"    AND {alias}.CD_CONTA = ?"
            f"    AND {condition.sql_condition(NORM_DS_CONTA_SQL.format(alias=alias))}"
            f")"
        )
        params.extend([condition.cd_conta, condition.ds_conta_normalized])
    return " AND ".join(clauses)


def rule_matches_sql(
    rules: list[StructuralRule],
    params: list[object],
) -> str:
    """Renderiza o resultado de cada regra estrutural como SELECT list.

    Renderiza as condições de cada regra estrutural como uma única expressão booleana
    O resultado dessa expressão recebe um alias rule_N_match padronizada por 
    :func:`rule_match_alias` e é reutilizado depois por profile_id e rule_applied.

    ### Args
        rules: Regras a avaliar.
        params: A lista de parâmetros acumulados é mutada in place.

    ### Returns
        A SELECT list da CTE ``rule_matches``, com uma coluna por regra, na ordem 
        de ``rules``.
    
    Referências: docs/profiles.md, docs/classificacao.md
    """
    if not rules:
        return "TRUE AS no_rule_match"

    matchings = [
        f"{rule_conditions_sql(rule, params)} AS {rule_match_alias(index)}"
        for index, rule in enumerate(rules)
    ]
    return ", ".join(matchings)


def classification_sql(rules: list[StructuralRule]) -> tuple[str, str]:
    """
    Renderiza as expressões SQL que definem ``profile_id`` e ``rule_applied`` de cada 
    empresa na consulta de classificação SQL_CLASSIFY.

    Recebe a lista de regras estruturais (STRUCTURAL_RULES) na ordem de precedência, 
    e gera dois ``CASE WHEN``: um para profile ``profile_id`` e outro para regra 
    aplicada ``rule_applied``.
    
    ### Returns
        Tupla ``(profile_id_sql, rule_applied_sql)``.

    Referências: docs/profiles.md, docs/classificacao.md
    """
    branches = [(f"rm.{rule_match_alias(index)}", rule) for index, rule in enumerate(rules)]

    if branches:
        profile_branches = " ".join(
            f"WHEN {expr} THEN {_sql_str(rule.profile_id)}" for expr, rule in branches
        )
        applied_branches = " ".join(
            f"WHEN {expr} THEN {_sql_str(rule.rule_applied)}" for expr, rule in branches
        )
    else:
        profile_branches = ""
        applied_branches = ""

    profile_sql = (
        f"CASE {profile_branches} ELSE {_sql_str(FALLBACK_PROFILE)} END"
        if profile_branches
        else f"CASE WHEN TRUE THEN {_sql_str(FALLBACK_PROFILE)} END"
    )

    return (
        profile_sql,
        f"CASE {applied_branches}"
        f" WHEN c.CNPJ_CIA IS NULL THEN 'default:sem_cadastro:sem_assinatura'"
        f" WHEN c.setor_ativ IS NULL OR trim(c.setor_ativ) = '' THEN 'default:setor_vazio'"
        f" ELSE 'default:setor:' || trim(c.setor_ativ)"
        f" END",
    )