"""SQL da classificação cadastral.

Só strings e funções de composição de texto. Nenhuma constante de tabela entra
aqui como literal: os nomes vêm das constantes em ``cvmdata.ingestion.tables`` e
são injetados por quem chama.
"""

from __future__ import annotations

UNIVERSE_COLS = "CNPJ_CIA"
DESCRIPTOR_COLS = "CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA"

# Uma linha por CNPJ, a mais recente por DT_INI_SIT. Sem filtro de SIT: empresa
# com demonstrativo é classificada mesmo cancelada ou suspensa.
SQL_CAD = """
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
    FROM {cad_table}
"""

# Relação vazia com as mesmas colunas, para quando cad_cia_aberta_raw não existe.
SQL_CAD_EMPTY = """
    SELECT
        CAST(NULL AS VARCHAR) AS CNPJ_CIA,
        CAST(NULL AS VARCHAR) AS CD_CVM,
        CAST(NULL AS VARCHAR) AS DENOM_SOCIAL,
        CAST(NULL AS VARCHAR) AS DENOM_COMERC,
        CAST(NULL AS VARCHAR) AS setor_ativ,
        CAST(NULL AS BIGINT) AS rn
    WHERE FALSE
"""

SQL_CLASSIFY = """
WITH universo AS (
    {universe}
),
cad AS (
    {cad_source}
),
descr AS (
    SELECT
        CNPJ_CIA,
        first(CD_CVM    ORDER BY DT_REFER DESC NULLS LAST, CD_CVM    ASC NULLS LAST) AS cd_cvm,
        first(DENOM_CIA ORDER BY DT_REFER DESC NULLS LAST, DENOM_CIA ASC NULLS LAST) AS denom_social
    FROM (
        {universe_descriptors}
    )
    GROUP BY CNPJ_CIA
),
sig AS (
    SELECT
        u.CNPJ_CIA AS cnpj_cia,
        {signature_flags}
    FROM universo u
)
INSERT INTO {classification}
    (cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ,
     profile_id, rule_applied, updated_at)
SELECT
    u.CNPJ_CIA                        AS cnpj_cia,
    COALESCE(CAST(c.CD_CVM AS VARCHAR), CAST(d.cd_cvm AS VARCHAR)) AS cd_cvm,
    COALESCE(c.DENOM_SOCIAL, d.denom_social) AS denom_social,
    c.DENOM_COMERC                    AS denom_comerc,
    c.setor_ativ                      AS setor_ativ,
    {profile_sql}                     AS profile_id,
    {rule_applied_sql}                AS rule_applied,
    current_timestamp                 AS updated_at
FROM universo u
LEFT JOIN cad c
    ON c.CNPJ_CIA = u.CNPJ_CIA
   AND c.rn = 1
LEFT JOIN descr d
    ON d.CNPJ_CIA = u.CNPJ_CIA
LEFT JOIN sig s
    ON s.cnpj_cia = u.CNPJ_CIA
{override_join}
"""


def union_select(tables: tuple[str, ...] | list[str], columns: str) -> str:
    """``UNION`` de ``SELECT columns FROM t`` para as tabelas informadas."""
    return "\n        UNION\n".join(f"SELECT {columns} FROM {t}" for t in tables)


def universe_sql(tables: list[str]) -> str:
    """``UNION`` de CNPJ entre as clean — quem de fato reportou demonstrativo."""
    return union_select(tables, UNIVERSE_COLS)


def descriptors_sql(tables: list[str]) -> str:
    """``UNION`` dos descritores (``CD_CVM``, ``DENOM_CIA``) das clean."""
    return union_select(tables, DESCRIPTOR_COLS)


def override_join(setor_profile_map: str | None) -> str:
    """``LEFT JOIN`` do override setorial, ou string vazia se não houver.

    Args:
        setor_profile_map: Tabela de override, ou ``None`` quando ela não existe.
    """
    if setor_profile_map is None:
        return ""
    return (
        f"LEFT JOIN {setor_profile_map} spm\n"
        "    ON spm.setor_ativ = c.setor_ativ\n"
        "   AND spm.active = TRUE"
    )