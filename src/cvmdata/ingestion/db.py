"""Conexão DuckDB e DDL das tabelas raw_*.

Demonstrativos em escopo (INDICATOR_DEMOS = BPA, BPP, DRE):
  Grupo A — Balanço (BPA, BPP): 14 colunas, sem DT_INI_EXERC
  Grupo B — Fluxo/Resultado (DRE): 15 colunas, com DT_INI_EXERC
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

# Demonstrativos necessários para os 7 indicadores planejados
INDICATOR_DEMOS: list[str] = ["BPA", "BPP", "DRE"]
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


_INDICATORS_DDL = """\
CREATE TABLE IF NOT EXISTS indicators (
    cnpj_cia  VARCHAR NOT NULL,
    dt_refer  DATE    NOT NULL,
    indicador VARCHAR NOT NULL,
    valor     DOUBLE,
    PRIMARY KEY (cnpj_cia, dt_refer, indicador)
);"""


def get_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Retorna conexão DuckDB persistente. Cria o arquivo se não existir."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    conn.execute("SET memory_limit = '1GB'")
    logger.debug("Conectado a %s", db_path)
    return conn


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria tabelas raw_* se ainda não existirem (idempotente)."""
    for demo in sorted(BALANCE_DEMOS):
        conn.execute(_BALANCE_DDL.format(demo=demo.lower()))

    for demo in sorted(FLOW_DEMOS):
        conn.execute(_FLOW_DDL.format(demo=demo.lower()))

    logger.info("Schema raw_* OK (%d tabelas)", len(INDICATOR_DEMOS))


def init_indicators_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria tabela `indicators` se ainda não existir (idempotente)."""
    conn.execute(_INDICATORS_DDL)
    logger.debug("Schema indicators OK")


# ── DDL Cadastral ──────────────────────────────────────────────────────────────

_CAD_RAW_DDL = """\
CREATE TABLE IF NOT EXISTS cad_cia_aberta_raw (
    -- Schema de referência — na prática a tabela é criada via CTAS em load_info_cad
    -- com auto_detect para preservar colunas desconhecidas (FR-014).
    CNPJ_CIA      VARCHAR,
    DENOM_CIA     VARCHAR,
    DENOM_COMERC  VARCHAR,
    CD_CVM        VARCHAR,
    SIT           VARCHAR,
    DT_INI_SIT    VARCHAR,
    TP_MERC       VARCHAR,
    CATEG_REG     VARCHAR,
    SETOR_ATIV    VARCHAR,
    DT_INC        VARCHAR,
    loaded_at     TIMESTAMPTZ
);"""

_SETOR_PROFILE_MAP_DDL = """\
CREATE TABLE IF NOT EXISTS setor_profile_map (
    setor_ativ  VARCHAR PRIMARY KEY,
    profile_id  VARCHAR NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ
);"""

_COMPANY_CLASSIFICATION_DDL = """\
CREATE TABLE IF NOT EXISTS company_classification (
    cnpj_cia     VARCHAR PRIMARY KEY,
    cd_cvm       VARCHAR,
    denom_social VARCHAR,
    denom_comerc VARCHAR,
    setor_ativ   VARCHAR,
    profile_id   VARCHAR NOT NULL,
    confidence   VARCHAR NOT NULL,
    rule_applied VARCHAR,
    updated_at   TIMESTAMPTZ
);"""

_CURATION_EVENTS_DDL = """\
CREATE TABLE IF NOT EXISTS classification_curation_events (
    cnpj_cia    VARCHAR NOT NULL,
    event_type  VARCHAR NOT NULL,
    details     VARCHAR,
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ,
    PRIMARY KEY (cnpj_cia, event_type)
);"""

_B3_TICKERS_DDL = """\
CREATE TABLE IF NOT EXISTS b3_tickers (
    cod_cvm       INTEGER,
    ticker_root   VARCHAR,
    company_name  VARCHAR,
    trading_name  VARCHAR,
    cnpj_digits   VARCHAR,
    status        VARCHAR,
    segment       VARCHAR,
    market        VARCHAR
);"""

# Mapeamentos iniciais de setor para profile (banking e arrendamento mercantil)
_SETOR_PROFILE_SEED: list[tuple[str, str]] = [
    ("Bancos", "banking"),
    ("Arrendamento Mercantil", "banking"),
    ("Intermediacao Financeira", "banking"),
]


def init_info_cad_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria tabelas cadastrais auxiliares se ainda não existirem (idempotente).

    Tabelas criadas aqui: setor_profile_map, company_classification,
    classification_curation_events.
    Nota: cad_cia_aberta_raw é criada via CTAS em load_info_cad (auto_detect).
    Semeia setor_profile_map com os mapeamentos iniciais (banking).
    """
    conn.execute(_SETOR_PROFILE_MAP_DDL)
    conn.execute(_COMPANY_CLASSIFICATION_DDL)
    conn.execute(_CURATION_EVENTS_DDL)

    # Semear setor_profile_map apenas onde não existe (INSERT OR IGNORE)
    for setor, profile in _SETOR_PROFILE_SEED:
        conn.execute(
            """
            INSERT OR IGNORE INTO setor_profile_map (setor_ativ, profile_id, active, updated_at)
            VALUES (?, ?, TRUE, current_timestamp)
            """,
            [setor, profile],
        )

    logger.info("Schema cadastral OK (4 tabelas)")


def init_b3_tickers_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria a tabela de tickers se ainda não existir (idempotente)."""
    conn.execute(_B3_TICKERS_DDL)
    logger.info("Schema b3_tickers OK")
