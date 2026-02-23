"""Normalização e deduplicação das tabelas raw_*.

Cria tabelas {table}_clean com:
  - Deduplicação via ROW_NUMBER particionado por
    (CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC):
    - BPA/BPP: ORDER BY VERSAO DESC — filtro ORDEM_EXERC = 'ÚLTIMO' descarta
      períodos comparativos anteriores (PENÚLTIMO é redundante em balanços snapshot)
    - DRE: ORDER BY DT_INI_EXERC ASC, VERSAO DESC — sem filtro ORDEM_EXERC;
      PENÚLTIMO é preservado pois é necessário para cálculo TTM nos indicadores.
      DT_INI_EXERC mínimo garante o valor acumulado YTD sobre o valor trimestral
      isolado (ambos podem ter o mesmo VERSAO a partir de Q2).
  - VL_CONTA recastado para DECIMAL(29,10)
  - CD_CVM normalizado para INTEGER (remove zeros à esquerda; NULL se não numérico)
  - Demais colunas mantidas sem conversão (DT_REFER e DT_FIM_EXERC já são DATE
    no schema raw_*; ESCALA_MOEDA registrada mas valores não convertidos)
"""
from __future__ import annotations

import logging

import duckdb

logger = logging.getLogger(__name__)

# SQL para BPA e BPP: deduplicação por versão mais alta, descarta PENÚLTIMO
_NORMALIZE_BALANCE_SQL = """\
CREATE OR REPLACE TABLE {clean} AS
SELECT * EXCLUDE (rn)
FROM (
    SELECT
        * REPLACE (
            VL_CONTA::DECIMAL(29, 10)         AS VL_CONTA,
            TRY_CAST(TRIM(CD_CVM) AS INTEGER) AS CD_CVM
        ),
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
            ORDER BY VERSAO DESC
        ) AS rn
    FROM {table}
)
WHERE rn = 1
  AND ORDEM_EXERC = 'ÚLTIMO'
"""

# SQL para DRE: duas diferenças em relação ao balance SQL:
#   1. ORDER BY DT_INI_EXERC ASC, VERSAO DESC — DT_INI mais antigo = YTD acumulado
#   2. Sem filtro ORDEM_EXERC                 — preserva PENÚLTIMO para TTM
_NORMALIZE_FLOW_SQL = """\
CREATE OR REPLACE TABLE {clean} AS
SELECT * EXCLUDE (rn)
FROM (
    SELECT
        * REPLACE (
            VL_CONTA::DECIMAL(29, 10)         AS VL_CONTA,
            TRY_CAST(TRIM(CD_CVM) AS INTEGER) AS CD_CVM
        ),
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
            ORDER BY DT_INI_EXERC ASC, VERSAO DESC
        ) AS rn
    FROM {table}
)
WHERE rn = 1
"""


def normalize_table(table: str, conn: duckdb.DuckDBPyConnection) -> int:
    """Cria ou substitui `{table}_clean` com dados deduplicados e tipados.

    Seleciona o template SQL adequado conforme o tipo de demonstrativo:
    - DRE (``table.endswith('dre')``): usa ``_NORMALIZE_FLOW_SQL`` que preserva
      ``PENÚLTIMO`` e ordena por ``DT_INI_EXERC ASC`` para garantir o YTD.
    - BPA/BPP: usa ``_NORMALIZE_BALANCE_SQL`` que filtra ``ORDEM_EXERC = 'ÚLTIMO'``.

    Args:
        table: Nome da tabela raw (ex: ``raw_bpa``, ``raw_dre``).
        conn:  Conexão DuckDB ativa.

    Returns:
        Número de linhas gravadas na tabela limpa.
    """
    clean = f"{table}_clean"
    sql = _NORMALIZE_FLOW_SQL if table.endswith("dre") else _NORMALIZE_BALANCE_SQL
    conn.execute(sql.format(table=table, clean=clean))
    count: int = conn.execute(f"SELECT COUNT(*) FROM {clean}").fetchone()[0]
    logger.info("  %s → %s: %d linhas", table, clean, count)
    return count


def normalize_all(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Normaliza todas as tabelas ``raw_*`` existentes no banco.

    Detecta automaticamente as tabelas via ``information_schema``, portanto
    funciona independentemente dos anos ou demonstrativos já carregados.

    Returns:
        Dict ``{table_name: row_count}`` para cada tabela normalizada.
    """
    rows = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name LIKE 'raw_%'
          AND table_name NOT LIKE '%_clean'
        ORDER BY table_name
        """
    ).fetchall()

    tables = [r[0] for r in rows]

    if not tables:
        logger.warning("Nenhuma tabela raw_* encontrada — rode 'load' primeiro")
        return {}

    logger.info("Normalizando %d tabela(s): %s", len(tables), ", ".join(tables))

    results: dict[str, int] = {}
    for table in tables:
        results[table] = normalize_table(table, conn)

    total = sum(results.values())
    logger.info(
        "Normalização concluída: %d tabela(s), %d linhas totais",
        len(results),
        total,
    )
    return results
