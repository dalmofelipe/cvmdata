"""Orquestração do cálculo de indicadores: fetch batch, cálculo, persistência."""

from __future__ import annotations

import logging

import duckdb

from cvmdata.ingestion.db import init_indicators_schema
from cvmdata.transform.indicators.balance import _fetch_all_components
from cvmdata.transform.indicators.build import IndicatorRow, _build_indicator_rows
from cvmdata.transform.indicators.ttm import Components, _fetch_all_dre_components

logger = logging.getLogger(__name__)

_CLEAN_TABLES = ("raw_bpa_clean", "raw_bpp_clean", "raw_dre_clean")


def _tables_available(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Quais das tabelas ``*_clean`` existem no banco."""
    rows = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name IN ({})
        """.format(", ".join(f"'{t}'" for t in _CLEAN_TABLES))
    ).fetchall()
    return {r[0] for r in rows}


def _collect_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None,
    tables: set[str],
) -> Components:
    """Funde componentes de balanço (BPA/BPP) e DRE (TTM) por (cnpj, dt_refer)."""
    has_balance = bool(tables & {"raw_bpa_clean", "raw_bpp_clean"})
    balance_comps = _fetch_all_components(conn, cnpj) if has_balance else {}
    dre_comps = _fetch_all_dre_components(conn, cnpj) if "raw_dre_clean" in tables else {}

    merged: Components = {}
    for key in set(balance_comps) | set(dre_comps):
        merged[key] = {**balance_comps.get(key, {}), **dre_comps.get(key, {})}

    return merged


def _persist_rows(conn: duckdb.DuckDBPyConnection, cnpj: str | None, rows: list[IndicatorRow]) -> None:
    """Substitui as linhas de ``indicators`` (do cnpj filtrado, ou todas) em uma transação."""
    conn.execute("BEGIN")
    try:
        if cnpj:
            conn.execute("DELETE FROM indicators WHERE cnpj_cia = ?", [cnpj])
        else:
            conn.execute("TRUNCATE indicators")

        if rows:
            cnpjs, dt_refers, indicadores, valores = zip(*rows)
            conn.execute(
                """
                INSERT INTO indicators (cnpj_cia, dt_refer, indicador, valor)
                SELECT
                    unnest(?) AS cnpj_cia, unnest(?)::DATE AS dt_refer,
                    unnest(?) AS indicador, unnest(?) AS valor
                """,
                [list(cnpjs), list(dt_refers), list(indicadores), list(valores)],
            )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def calculate_all(conn: duckdb.DuckDBPyConnection, cnpj: str | None = None) -> int:
    """Calcula todos os indicadores fundamentalistas para as empresas/períodos disponíveis.

    Usa duas queries batch (``_fetch_all_components`` + ``_fetch_all_dre_components``,
    a última já com TTM resolvido em SQL) em vez de N round-trips por par
    (cnpj, dt_refer), e persiste tudo em uma única transação via UNNEST
    (ver ``_persist_rows``).

    Args:
        conn: Conexão DuckDB com as tabelas ``*_clean`` já criadas.
        cnpj: Se fornecido, processa apenas essa empresa.

    Returns:
        Número total de registros gravados em ``indicators``.
    """
    init_indicators_schema(conn)

    tables = _tables_available(conn)
    if not tables:
        logger.warning("Tabelas *_clean ausentes — rode 'normalize' primeiro")
        return 0

    components = _collect_components(conn, cnpj, tables)
    if not components:
        logger.warning("Nenhum dado nas tabelas *_clean — rode 'normalize' primeiro")
        return 0

    logger.info("Calculando indicadores para %d empresa/período(s)…", len(components))

    all_rows: list[IndicatorRow] = []
    for (cnpj_cia, dt_refer), comp in components.items():
        try:
            all_rows.extend(_build_indicator_rows(cnpj_cia, dt_refer, comp))
        except Exception:
            logger.exception("Erro ao calcular indicadores para %s %s — pulando", cnpj_cia, dt_refer)

    _persist_rows(conn, cnpj, all_rows)

    logger.info("Indicadores: %d registros gravados", len(all_rows))
    return len(all_rows)
