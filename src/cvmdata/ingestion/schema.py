"""DDL do DuckDB e reconciliação de bancos legados.

Todo ``CREATE TABLE`` de produção vive aqui. Fica separado de
:mod:`cvmdata.ingestion.database` (conexão e orquestração de carga) porque são
duas coisas diferentes: abrir o banco, e definir o banco. O módulo é o **sítio
de declaração** dos nomes de tabela — é o único lugar onde o literal é aceito,
e ``tests/unit/test_tables.py`` barra o literal em qualquer outro SQL.

Cada ``init_*`` é idempotente e pode rodar em qualquer ordem.
"""

from __future__ import annotations

import logging

import duckdb

from cvmdata.ingestion.catalog import BALANCE_DEMOS, CATALOG, FLOW_DEMOS, DatasetType
from cvmdata.ingestion.tables import (
    TB_COMPANY_CLASSIFICATION,
    TB_SETOR_PROFILE_MAP,
)

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

SETOR_PROFILE_MAP_DDL = """\
CREATE TABLE IF NOT EXISTS setor_profile_map (
    setor_ativ  VARCHAR PRIMARY KEY,
    profile_id  VARCHAR NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ
);"""


# ── Migração de bancos legados ───────────────────────────────────────────────

# Setores que o seed antigo mandava para banking. A classificação agora é
# estrutural, então essas linhas são removidas de bancos legados — mantê-las
# sobreporia a assinatura e devolveria o bug do setor como discriminador.
LEGACY_BANKING_SETORES: tuple[str, ...] = (
    "Bancos",
    "Arrendamento Mercantil",
    "Intermediacao Financeira",
)

LEGACY_CURATION_TABLE = "classification_curation_events"


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(
        conn.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE table_name = ?", [table]
        ).fetchone()[0]
    )


def _column_names(conn: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM duckdb_columns() WHERE table_name = ?", [table]
    ).fetchall()
    return [r[0] for r in rows]


def reconcile_legacy_classification(conn: duckdb.DuckDBPyConnection) -> None:
    """Adequa bancos criados antes da classificação estrutural (idempotente).

    Três mudanças, todas sem perder dado do usuário:

    1. remove a coluna ``confidence`` de ``company_classification`` — o perfil
       passou a ser asserção estrutural, não uma inferência probabilística,
       e nada mais a escreve;
    2. apaga as linhas de ``setor_profile_map`` que o seed antigo criou, e só
       elas: overrides manuais continuam intactos;
    3. descarta ``classification_curation_events``, que registrava as curation
       events da versão anterior do classificador.
    """
    if _table_exists(conn, TB_COMPANY_CLASSIFICATION):
        if "confidence" in _column_names(conn, TB_COMPANY_CLASSIFICATION):
            conn.execute(
                f"ALTER TABLE {TB_COMPANY_CLASSIFICATION} DROP COLUMN confidence"
            )
            logger.info("Coluna confidence removida de company_classification (legado)")

    if _table_exists(conn, TB_SETOR_PROFILE_MAP):
        placeholders = ", ".join("?" for _ in LEGACY_BANKING_SETORES)
        # DuckDB devolve rowcount = -1 em DELETE, então a contagem vem antes.
        legadas = conn.execute(
            f"SELECT count(*) FROM {TB_SETOR_PROFILE_MAP} "
            f"WHERE setor_ativ IN ({placeholders}) AND profile_id = 'banking'",
            list(LEGACY_BANKING_SETORES),
        ).fetchone()[0]
        if legadas:
            conn.execute(
                f"DELETE FROM {TB_SETOR_PROFILE_MAP} "
                f"WHERE setor_ativ IN ({placeholders}) AND profile_id = 'banking'",
                list(LEGACY_BANKING_SETORES),
            )
            logger.warning(
                f"Removidas {legadas} linhas do seed setorial legado em "
                f"{TB_SETOR_PROFILE_MAP} — a assinatura estrutural decide o perfil"
            )

    if _table_exists(conn, LEGACY_CURATION_TABLE):
        conn.execute(f"DROP TABLE {LEGACY_CURATION_TABLE}")
        logger.info(f"Tabela {LEGACY_CURATION_TABLE} removida (legado)")


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
    """Cria tabelas cadastrais auxiliares se ainda não existirem (idempotente).

    Tabelas criadas aqui: setor_profile_map, company_classification.
    Nota: cad_cia_aberta_raw é criada via CTAS em load_info_cad (auto_detect).

    ``setor_profile_map`` nasce **vazia**: o perfil vem da assinatura estrutural
    (ver :mod:`cvmdata.transform.profile`), e setor de atividade não é
    discriminador de layout — bancos reportam layout padrão e holdings de
    crédito reportam layout financeiro. A tabela continua sendo o ponto de
    override manual, e também de mapeamento para perfis que a estrutura ainda
    não cobre; o seed antigo ("Bancos"/"Arrendamento Mercantil"/"Intermediacao
    Financeira" → banking) foi removido porque mapeava por setor o que a
    estrutura resolve melhor.

    A função também reconcilia bancos já existentes — ver
    :func:`reconcile_legacy_classification`. O ``CREATE TABLE IF NOT EXISTS``
    não altera tabela que já existe, então um banco criado antes da mudança
    continuaria com a coluna ``confidence`` e com o seed setorial, e o
    ``INSERT`` de :func:`cvmdata.transform.info_cad.classify_info_cad` passaria
    a falhar.
    """
    reconcile_legacy_classification(conn)
    conn.execute(SETOR_PROFILE_MAP_DDL)
    conn.execute(COMPANY_CLASSIFICATION_DDL)

    logger.info("Schema cadastral OK (2 tabelas)")