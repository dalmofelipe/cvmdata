"""Ingestão de CSVs extraídos dos ZIPs CVM para o DuckDB.

Apenas arquivos consolidados (_con_) são aceitos — individuais (_ind_) são
ignorados em todas as etapas (extração, parse e load).

Padrão de nome de arquivo (CVM usa maiúsculas no demo):
  {source}_cia_aberta_{DEMO}_con_{year}.csv
  ex: itr_cia_aberta_BPA_con_2024.csv

Cada arquivo é carregado na tabela raw_{demo} com colunas
de metadata: source, year, scope.

Idempotência: rows existentes para (source, year, scope) são
deletadas antes de cada INSERT.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import duckdb

from cvmdata.ingestion.db import (
    BALANCE_DEMOS,
    FLOW_DEMOS,
    INDICATOR_DEMOS,
    init_b3_tickers_schema,
    init_schema,
)
from cvmdata.transform.account_map import ACCOUNT_MAP

logger = logging.getLogger(__name__)

# Regex extrai (source, demo, year) do basename — apenas scope=con
# Ex: itr_cia_aberta_BPA_con_2024.csv
_FILENAME_RE = re.compile(
    r"^(?P<source>itr|dfp)_cia_aberta_(?P<demo>[A-Z_]+)_(?P<scope>con)_(?P<year>\d{4})\.csv$",
    re.IGNORECASE,
)

# Contas necessárias para os indicadores — filtragem aplicada no load
_ACCOUNT_CODES_SQL = ", ".join(f"'{k}'" for k in sorted(ACCOUNT_MAP.keys()))

_COMMON_COLS_HEAD = """\
    CNPJ_CIA::VARCHAR,
    CAST(DT_REFER AS DATE),
    VERSAO::SMALLINT,
    DENOM_CIA::VARCHAR,
    CD_CVM::VARCHAR,
    GRUPO_DFP::VARCHAR,
    MOEDA::VARCHAR,
    ESCALA_MOEDA::VARCHAR,
    ORDEM_EXERC::VARCHAR,"""

_COMMON_COLS_TAIL = """\
    CD_CONTA::VARCHAR,
    DS_CONTA::VARCHAR,
    TRY_CAST(VL_CONTA AS DOUBLE),
    ST_CONTA_FIXA::VARCHAR"""

_ALT_COLS: dict[frozenset, str] = {
    frozenset(BALANCE_DEMOS): "CAST(DT_FIM_EXERC AS DATE),",
    frozenset(FLOW_DEMOS):    "CAST(DT_INI_EXERC AS DATE), CAST(DT_FIM_EXERC AS DATE),",
    frozenset(INDICATOR_DEMOS): (
        "CAST(DT_INI_EXERC AS DATE), CAST(DT_FIM_EXERC AS DATE), COLUNA_DF::VARCHAR,"
    ),
}


def _alt_cols_for(demo: str) -> str:
    demo_upper = demo.upper()
    for demos, cols in _ALT_COLS.items():
        if demo_upper in demos:
            return cols
    raise ValueError(f"Demo desconhecido: {demo!r}")


def _build_insert_sql(csv_path: Path, demo: str, source: str, year: int, scope: str) -> str:
    """Monta o SQL de INSERT conforme o grupo de schema do demonstrativo.

    Filtra apenas as linhas cujo CD_CONTA está no ACCOUNT_MAP, descartando
    todas as contas irrelevantes para os indicadores antes da persistência.
    """
    table = f"raw_{demo.lower()}"
    fpath = csv_path.as_posix()
    alt_cols = _alt_cols_for(demo)

    query = "\n        ".join([
        _COMMON_COLS_HEAD,
        alt_cols,
        _COMMON_COLS_TAIL,
    ])

    return f"""
    INSERT INTO {table}
    SELECT
        {query},
        '{source}'::VARCHAR  AS source,
        {year}::SMALLINT     AS year,
        '{scope}'::VARCHAR   AS scope
    FROM read_csv(
        '{fpath}',
        delim    = ';',
        header   = true,
        encoding = 'cp1252',
        nullstr  = ''
    )
    WHERE CD_CONTA::VARCHAR IN ({_ACCOUNT_CODES_SQL});"""


def parse_csv_filename(path: Path) -> tuple[str, str, str, int] | None:
    """Extrai (demo, scope, source, year) do nome do arquivo.

    Retorna None se o arquivo não for um demonstrativo consolidado (_con_)
    de um demo em escopo. Arquivos _ind_ não casam com o regex e retornam None.
    """
    m = _FILENAME_RE.match(path.name)
    if not m:
        return None
    demo = m.group("demo").upper()
    if demo not in INDICATOR_DEMOS:
        logger.debug("Demo desconhecido '%s', pulando %s", demo, path.name)
        return None
    return demo, "con", m.group("source").lower(), int(m.group("year"))


def load_csv(
    conn: duckdb.DuckDBPyConnection,
    csv_path: Path,
    demo: str,
    source: str,
    year: int,
    scope: str,
) -> int:
    """Carrega um CSV consolidado na tabela raw_{demo}. Retorna linhas inseridas.

    Idempotente: deleta linhas existentes para (source, year, scope) antes do INSERT.
    Levanta ValueError se scope != 'con' — apenas consolidado é suportado.
    """
    if scope != "con":
        raise ValueError(
            f"load_csv: escopo '{scope}' não suportado — apenas 'con' (consolidado) é aceito. "
            f"Arquivo: {csv_path.name}"
        )
    table = f"raw_{demo.lower()}"

    # Remove dados anteriores desse arquivo específico
    conn.execute(
        f"DELETE FROM {table} WHERE source = ? AND year = ? AND scope = ?",
        [source, year, scope],
    )

    sql = _build_insert_sql(csv_path, demo, source, year, scope)
    conn.execute(sql)

    count = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE source = ? AND year = ? AND scope = ?",
        [source, year, scope],
    ).fetchone()[0]

    logger.info("  %s/%s/%s/%s → %d linhas", demo, scope, source, year, count)
    return count


def load_source_year(
    conn: duckdb.DuckDBPyConnection,
    source: str,
    year: int,
    raw_dir: Path,
) -> dict[str, int]:
    """Carrega todos os CSVs de um source+year no DuckDB.

    Escaneia raw_dir/{source}/{year}/*.csv, identifica demostrativos via filename e
    chama load_csv para cada um.

    Retorna dict {"{DEMO}/{scope}": row_count} para os arquivos carregados.
    """
    init_schema(conn)

    csv_dir = raw_dir / source / str(year)
    if not csv_dir.exists():
        logger.warning("Diretório não encontrado: %s — rode 'download' primeiro", csv_dir)
        return {}

    results: dict[str, int] = {}
    csv_files = sorted(csv_dir.glob("*.csv"))

    if not csv_files:
        logger.warning("Nenhum CSV encontrado em %s", csv_dir)
        return {}

    logger.info("Carregando %d arquivos de %s …", len(csv_files), csv_dir)

    for csv_path in csv_files:
        parsed = parse_csv_filename(csv_path)
        if parsed is None:
            logger.debug("Pulando %s (não é demo com scope)", csv_path.name)
            continue

        demo, scope, _src, _yr = parsed
        try:
            count = load_csv(conn, csv_path, demo, source, year, scope)
            results[f"{demo}/{scope}"] = count
        except Exception as exc:
            logger.error("Erro ao carregar %s: %s", csv_path.name, exc)
            raise

    total = sum(results.values())
    logger.info("Load %s/%d concluído: %d linhas em %d tabelas", source, year, total, len(results))
    return results


# ── Informação Cadastral CVM ──────────────────────────────────────────────────────────────


def load_info_cad(
    conn: duckdb.DuckDBPyConnection,
    csv_path: Path,
) -> int:
    """Carrega cad_cia_aberta.csv por recarga total (drop + insert).

    - Preserva todas as colunas via auto_detect (schema inferido).
    - Adiciona coluna `loaded_at` com timestamp atual.
    - Usa transação: falha não corrompe tabela prévia.
    - Retorna contagem de linhas inseridas.

    Valida SC-001: linhas CSV == linhas inseridas.
    """
    from cvmdata.ingestion.db import init_info_cad_schema

    init_info_cad_schema(conn)

    fpath = csv_path.as_posix()

    # Contar linhas do CSV antes de carregar (SC-001)
    csv_count = conn.execute(
        f"SELECT COUNT(*) FROM read_csv('{fpath}', delim=';', header=true, encoding='latin-1')"
    ).fetchone()[0]
    logger.info("CSV cadastral: %d linhas", csv_count)

    # CTAS: CREATE OR REPLACE atomically replaces the table with auto-detected schema.
    # This preserves all columns from CVM CSV (includes unknown future columns per FR-014).
    # Wrapped in explicit transaction so a failed SELECT rolls back without leaving
    # a partial/corrupt table state (T011 rollback guard).
    conn.execute("BEGIN")
    try:
        conn.execute(f"""
            CREATE OR REPLACE TABLE cad_cia_aberta_raw AS
            SELECT
                *,
                current_timestamp AS loaded_at
            FROM read_csv(
                '{fpath}',
                delim    = ';',
                header   = true,
                encoding = 'latin-1',
                nullstr  = ''
            )
        """)
        inserted = conn.execute("SELECT COUNT(*) FROM cad_cia_aberta_raw").fetchone()[0]
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    # SC-001: validar paridade
    if inserted != csv_count:
        logger.warning("SC-001 FAIL: CSV=%d linhas, raw=%d linhas inseridas", csv_count, inserted)
    else:
        logger.info("SC-001 OK: %d linhas — CSV == raw", inserted)

    return inserted


# ── Tickers B3 ───────────────────────────────────────────────────────────────────────────


def _build_b3_tickers_sql(json_glob: Path) -> str:
    """Monta o SQL de carga da tabela de tickers a partir dos JSONs do B3."""
    fpath = json_glob.as_posix()
    return f"""
    CREATE OR REPLACE TABLE b3_tickers AS
    SELECT
        TRY_CAST(r.codeCVM AS INTEGER) AS cod_cvm,
        r.issuingCompany::VARCHAR      AS ticker_root,
        r.companyName::VARCHAR         AS company_name,
        r.tradingName::VARCHAR         AS trading_name,
        regexp_replace(COALESCE(r.cnpj::VARCHAR, ''), '[^0-9]', '', 'g') AS cnpj_digits,
        r.status::VARCHAR              AS status,
        r.segment::VARCHAR             AS segment,
        r.market::VARCHAR              AS market
    FROM read_json_auto('{fpath}') AS p,
        UNNEST(p.results) AS t(r)
    WHERE r.status::VARCHAR = 'A';"""


def load_b3_tickers(
    conn: duckdb.DuckDBPyConnection,
    tickers_dir: Path,
    *,
    glob_pattern: str = "page_*.json",
) -> int:
    """Carrega tickers da B3 a partir dos JSONs page_*.json.

    Retorna o total de linhas gravadas. Se a pasta ou os arquivos não existirem,
    registra warning e retorna 0 sem falhar o pipeline principal.
    """
    if not tickers_dir.exists():
        logger.warning("Diretório de tickers não encontrado: %s", tickers_dir)
        logger.warning("Verifique processamento do github/dalmofelipe/b3-tickers no CI")
        return 0

    files = sorted(tickers_dir.glob(glob_pattern))
    if not files:
        logger.warning(
            "Nenhum JSON de tickers encontrado em %s usando %s",
            tickers_dir,
            glob_pattern,
        )
        return 0

    init_b3_tickers_schema(conn)

    sql = _build_b3_tickers_sql(tickers_dir / glob_pattern)
    conn.execute(sql)

    row = conn.execute(f"SELECT COUNT(*) FROM b3_tickers").fetchone()
    assert row is not None, "[load_b3_tickers] Não foi possível contar linhas em b3_tickers"
    count: int = row[0]

    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_b3_tickers_cod_cvm ON b3_tickers (cod_cvm)")

    logger.info("Tickers B3 carregados: %d linhas em b3_tickers", count)
    return count
