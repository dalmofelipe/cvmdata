"""Conexão DuckDB e DDL das tabelas raw_*.

Demonstrativos em escopo (INDICATOR_DEMOS = BPA, BPP, DRE):
  Grupo A — Balanço (BPA, BPP): 14 colunas, sem DT_INI_EXERC
  Grupo B — Fluxo/Resultado (DRE): 15 colunas, com DT_INI_EXERC

[ADR 2026-02-20]: DFC_MD, DFC_MI, DMPL, DRA, DVA descartados — nenhuma
conta desses demonstrativos é necessária para os 7 indicadores planejados.
"""
from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

# Demonstrativos necessários para os 7 indicadores planejados
INDICATOR_DEMOS: list[str] = ["BPA", "BPP", "DRE"]
DEMOS: list[str] = INDICATOR_DEMOS  # alias mantido para retrocompatibilidade
SCOPES: list[str] = ["con", "ind"]

# Grupos por schema real (verificado nos CSVs 2024)
BALANCE_DEMOS: frozenset[str] = frozenset({"BPA", "BPP"})
FLOW_DEMOS: frozenset[str] = frozenset({"DRE"})

# ── DDL ───────────────────────────────────────────────────────────────────────

# Grupo A: BPA, BPP — 14 colunas (sem DT_INI_EXERC)
_BALANCE_DDL = """\
CREATE TABLE IF NOT EXISTS raw_{demo} (
    CNPJ_CIA      VARCHAR,
    DT_REFER      DATE,
    VERSAO        SMALLINT,
    DENOM_CIA     VARCHAR,
    CD_CVM        VARCHAR,
    GRUPO_DFP     VARCHAR,
    MOEDA         VARCHAR,
    ESCALA_MOEDA  VARCHAR,
    ORDEM_EXERC   VARCHAR,
    DT_FIM_EXERC  DATE,
    CD_CONTA      VARCHAR,
    DS_CONTA      VARCHAR,
    VL_CONTA      DOUBLE,
    ST_CONTA_FIXA VARCHAR,
    source        VARCHAR,
    year          SMALLINT,
    scope         VARCHAR
);"""

# Grupo B: DRE — 15 colunas (com DT_INI_EXERC)
_FLOW_DDL = """\
CREATE TABLE IF NOT EXISTS raw_{demo} (
    CNPJ_CIA      VARCHAR,
    DT_REFER      DATE,
    VERSAO        SMALLINT,
    DENOM_CIA     VARCHAR,
    CD_CVM        VARCHAR,
    GRUPO_DFP     VARCHAR,
    MOEDA         VARCHAR,
    ESCALA_MOEDA  VARCHAR,
    ORDEM_EXERC   VARCHAR,
    DT_INI_EXERC  DATE,
    DT_FIM_EXERC  DATE,
    CD_CONTA      VARCHAR,
    DS_CONTA      VARCHAR,
    VL_CONTA      DOUBLE,
    ST_CONTA_FIXA VARCHAR,
    source        VARCHAR,
    year          SMALLINT,
    scope         VARCHAR
);"""


def get_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Retorna conexão DuckDB persistente. Cria o arquivo se não existir."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    logger.debug("Conectado a %s", db_path)
    return conn


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria tabelas raw_* se ainda não existirem (idempotente)."""
    for demo in sorted(BALANCE_DEMOS):
        conn.execute(_BALANCE_DDL.format(demo=demo.lower()))

    for demo in sorted(FLOW_DEMOS):
        conn.execute(_FLOW_DDL.format(demo=demo.lower()))

    logger.info("Schema raw_* OK (%d tabelas)", len(DEMOS))
