"""Normalização e deduplicação das tabelas raw_*.

Cria tabelas {table}_clean com:
  - Deduplicação via ROW_NUMBER particionado por
    (CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC), mantendo VERSAO mais alta
  - Filtro ORDEM_EXERC = 'ÚLTIMO' — descarta períodos comparativos anteriores
  - VL_CONTA recastado para DECIMAL(29,10)
  - CD_CVM normalizado para INTEGER (remove zeros à esquerda; NULL se não numérico)
  - Demais colunas mantidas sem conversão (DT_REFER e DT_FIM_EXERC já são DATE
    no schema raw_*; ESCALA_MOEDA registrada mas valores não convertidos)
"""
from __future__ import annotations

import logging

import duckdb

logger = logging.getLogger(__name__)

_NORMALIZE_SQL = """\
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


def normalize_table(table: str, conn: duckdb.DuckDBPyConnection) -> int:
    """Cria ou substitui `{table}_clean` com dados deduplicados e tipados.

    Args:
        table: Nome da tabela raw (ex: ``raw_bpa``).
        conn:  Conexão DuckDB ativa.

    Returns:
        Número de linhas gravadas na tabela limpa.
    """
    clean = f"{table}_clean"
    conn.execute(_NORMALIZE_SQL.format(table=table, clean=clean))
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
