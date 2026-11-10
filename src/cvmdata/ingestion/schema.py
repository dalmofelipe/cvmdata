from __future__ import annotations

import logging

import duckdb

from cvmdata.ingestion.catalog import BALANCE_DEMOS, CATALOG, FLOW_DEMOS, DatasetType

logger = logging.getLogger(__name__)

# ── DDL do catálogo ──────────────────────────────────────────────────────────

# Grupo A: BPA, BPP — 14 colunas (sem DT_INI_EXERC)
# O nome da tabela vem de CvmDataset.table, no catálogo.
BALANCE_DDL = """\
CREATE TABLE IF NOT EXISTS {table} (
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
FLOW_DDL = """\
CREATE TABLE IF NOT EXISTS {table} (
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

# Composicao Capital — tabela direta (sem CD_CONTA, sem filtro)
COMPOSICAO_CAPITAL_DDL = """\
CREATE TABLE IF NOT EXISTS composicao_capital (
    CNPJ_CIA                 VARCHAR,
    DT_REFER                 DATE,
    VERSAO                   INTEGER,
    DENOM_CIA                VARCHAR,
    QT_ACAO_ORDIN_CAP_INTEGR BIGINT,
    QT_ACAO_PREF_CAP_INTEGR  BIGINT,
    QT_ACAO_TOTAL_CAP_INTEGR BIGINT,
    QT_ACAO_ORDIN_TESOURO    BIGINT,
    QT_ACAO_PREF_TESOURO     BIGINT,
    QT_ACAO_TOTAL_TESOURO    BIGINT,
    source                   VARCHAR,
    year                     SMALLINT
);"""

INDICATORS_DDL = """\
CREATE TABLE IF NOT EXISTS indicators (
    cnpj_cia  VARCHAR NOT NULL,
    dt_refer  DATE    NOT NULL,
    indicador VARCHAR NOT NULL,
    valor     DOUBLE
);"""

B3_TICKERS_DDL = """\
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

# ── DDL cadastral ────────────────────────────────────────────────────────────

CAD_RAW_DDL = """\
CREATE TABLE IF NOT EXISTS cad_cia_aberta_raw (
    -- Schema de referência — na prática a tabela é criada via CTAS em
    -- load_info_cad com auto_detect para preservar colunas desconhecidas
    -- (FR-014).
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

COMPANY_CLASSIFICATION_DDL = """\
CREATE TABLE IF NOT EXISTS company_classification (
    cnpj_cia     VARCHAR PRIMARY KEY,
    cd_cvm       VARCHAR,
    denom_social VARCHAR,
    denom_comerc VARCHAR,
    setor_ativ   VARCHAR,
    profile_id   VARCHAR NOT NULL,
    rule_applied VARCHAR,
    updated_at   TIMESTAMPTZ
);"""


# ── Inicialização ────────────────────────────────────────────────────────────


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria tabelas do catálogo se ainda não existirem (idempotente)."""
    for key, ds in CATALOG.items():
        if key in BALANCE_DEMOS:
            conn.execute(BALANCE_DDL.format(table=ds.table))
        elif key in FLOW_DEMOS:
            conn.execute(FLOW_DDL.format(table=ds.table))
        elif ds.type == DatasetType.DIRECT_INSERT:
            conn.execute(COMPOSICAO_CAPITAL_DDL)

    logger.info("Schema OK (%d tabelas no catálogo)", len(CATALOG))


def init_indicators_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria ``indicators`` se ainda não existir (idempotente)."""
    conn.execute(INDICATORS_DDL)
    logger.debug("Schema indicators OK")


def init_b3_tickers_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria ``b3_tickers`` se ainda não existir (idempotente)."""
    conn.execute(B3_TICKERS_DDL)
    logger.info("Schema b3_tickers OK")


def init_info_cad_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria ``company_classification`` se ainda não existir (idempotente)."""
    conn.execute(COMPANY_CLASSIFICATION_DDL)
    logger.info("Schema cadastral OK (1 tabela)")