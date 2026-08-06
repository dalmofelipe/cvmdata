"""Ingestão de CSVs extraídos dos ZIPs CVM para o DuckDB.

O catálogo em core/catalog.py define quais datasets são processados
e como cada um é carregado (demonstrativo com filtro de contas vs. tabela direta).

Idempotência: rows existentes para (source, year) são deletadas antes de cada INSERT.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from cvmdata.ingestion.catalog import CATALOG, DatasetType
from cvmdata.ingestion.db import init_b3_tickers_schema, init_schema
from cvmdata.ingestion.encoding import _utf8_csv
from cvmdata.transform.account_map import ACCOUNT_MAP

logger = logging.getLogger(__name__)


_ACCOUNT_CODES: list[str] = sorted(ACCOUNT_MAP.keys())


_COLUMNS_SQL_TMPL = """\
    CNPJ_CIA::VARCHAR,
    CAST(DT_REFER AS DATE),
    VERSAO::SMALLINT,
    DENOM_CIA::VARCHAR,
    CD_CVM::VARCHAR,
    GRUPO_DFP::VARCHAR,
    MOEDA::VARCHAR,
    ESCALA_MOEDA::VARCHAR,
    ORDEM_EXERC::VARCHAR,
    {alt_cols}
    CD_CONTA::VARCHAR,
    DS_CONTA::VARCHAR,
    TRY_CAST(VL_CONTA AS DOUBLE),
    ST_CONTA_FIXA::VARCHAR"""

_ALT_COLS: dict[str, str] = {
    "BPA": "CAST(DT_FIM_EXERC AS DATE),",
    "BPP": "CAST(DT_FIM_EXERC AS DATE),",
    "DRE": "CAST(DT_INI_EXERC AS DATE), CAST(DT_FIM_EXERC AS DATE),",
}


def _alt_cols_for(demo: str) -> str:
    try:
        return _ALT_COLS[demo.upper()]
    except KeyError:
        raise ValueError(f"Demo desconhecido: {demo!r}")


def _match_dataset(filename: str) -> tuple[str, DatasetType] | None:
    """Retorna (key, type) se o filename corresponde a algum dataset do catálogo."""
    fname = filename.lower()
    for key, ds in CATALOG.items():
        if ds.pattern in fname:
            return key, ds.type
    return None


def _build_demo_insert_sql(csv_path: Path, demo: str, source: str, year: int, scope: str) -> str:
    """Monta o SQL de INSERT para demonstrativos (BPA, BPP, DRE).

    Filtra apenas as linhas cujo CD_CONTA está no ACCOUNT_MAP.
    """
    table = f"raw_{demo.lower()}"
    fpath = csv_path.as_posix()
    query = _COLUMNS_SQL_TMPL.format(alt_cols=_alt_cols_for(demo))

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
        nullstr  = ''
    )
    WHERE CD_CONTA::VARCHAR = ANY(?);"""


def load_csv(
    conn: duckdb.DuckDBPyConnection,
    csv_path: Path,
    demo: str,
    source: str,
    year: int,
    scope: str = "con",
) -> int:
    """Carrega um CSV de demonstrativo (BPA, BPP, DRE) na tabela raw_{demo}.

    Idempotente: deleta linhas de (source, year, scope) antes do INSERT.

    Mantida como API pública para testes e compatibilidade.
    """
    if scope != "con":
        raise ValueError(
            f"load_csv: escopo '{scope}' não suportado — apenas 'con' (consolidado) é aceito. "
            f"Arquivo: {csv_path.name}"
        )
    table = f"raw_{demo.lower()}"

    conn.execute(
        f"DELETE FROM {table} WHERE source = ? AND year = ? AND scope = ?",
        [source, year, scope],
    )

    with _utf8_csv(csv_path) as safe_path:
        sql = _build_demo_insert_sql(safe_path, demo, source, year, scope)
        conn.execute(sql, [_ACCOUNT_CODES])

    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE source = ? AND year = ? AND scope = ?",
        [source, year, scope],
    ).fetchone()
    assert row is not None
    count: int = row[0]

    logger.info("  %s/%s/%s/%s → %d linhas", demo, scope, source, year, count)
    return count


def _build_comp_capital_insert_sql(csv_path: Path, source: str, year: int) -> str:
    """Monta o SQL de INSERT para composicao_capital (sem filtro de CD_CONTA)."""
    fpath = csv_path.as_posix()
    return f"""
    INSERT INTO composicao_capital
    SELECT
        CNPJ_CIA::VARCHAR,
        TRY_CAST(DT_REFER AS DATE),
        VERSAO::INTEGER,
        DENOM_CIA::VARCHAR,
        TRY_CAST(QT_ACAO_ORDIN_CAP_INTEGR AS BIGINT),
        TRY_CAST(QT_ACAO_PREF_CAP_INTEGR AS BIGINT),
        TRY_CAST(QT_ACAO_TOTAL_CAP_INTEGR AS BIGINT),
        TRY_CAST(QT_ACAO_ORDIN_TESOURO AS BIGINT),
        TRY_CAST(QT_ACAO_PREF_TESOURO AS BIGINT),
        TRY_CAST(QT_ACAO_TOTAL_TESOURO AS BIGINT),
        '{source}'::VARCHAR AS source,
        {year}::SMALLINT    AS year
    FROM read_csv(
        '{fpath}',
        delim    = ';',
        header   = true,
        nullstr  = ''
    );"""


def _load_composicao_capital_csv(
    conn: duckdb.DuckDBPyConnection,
    csv_path: Path,
    source: str,
    year: int,
) -> int:
    """Carrega um CSV de composicao_capital na tabela composicao_capital.

    Idempotente: deleta linhas de (source, year) antes do INSERT.
    """
    conn.execute("DELETE FROM composicao_capital WHERE source = ? AND year = ?", [source, year])

    with _utf8_csv(csv_path) as safe_path:
        sql = _build_comp_capital_insert_sql(safe_path, source, year)
        conn.execute(sql)

    row = conn.execute(
        "SELECT COUNT(*) FROM composicao_capital WHERE source = ? AND year = ?",
        [source, year]
    ).fetchone()
    count: int = row[0] if row else 0

    logger.info("  composicao_capital/%s/%s → %d linhas", source, year, count)
    return count


def load_source_year(
    conn: duckdb.DuckDBPyConnection,
    source: str,
    year: int,
    raw_dir: Path,
) -> dict[str, int]:
    """Carrega todos os CSVs de um source+year no DuckDB.

    Escaneia raw_dir/{source}/{year}/*.csv, identifica datasets via catálogo e
    chama o método de carga adequado (demonstrativo vs. tabela direta).

    Retorna dict com "{key}": row_count para os arquivos carregados.
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
        matched = _match_dataset(csv_path.name)
        if matched is None:
            logger.debug("Pulando %s (não está no catálogo)", csv_path.name)
            continue

        key, ds_type = matched
        try:
            if ds_type == DatasetType.STATEMENT:
                count = load_csv(conn, csv_path, key, source, year)
            else:
                count = _load_composicao_capital_csv(conn, csv_path, source, year)
            results[key] = count
        except Exception as exc:
            logger.error("Erro ao carregar %s: %s", csv_path.name, exc)
            raise

    total = sum(results.values())
    logger.info("Load %s/%d concluído: %d linhas em %d datasets", source, year, total, len(results))
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

    with _utf8_csv(csv_path) as safe_path:
        fpath = safe_path.as_posix()

        row = conn.execute(
            f"SELECT COUNT(*) FROM read_csv('{fpath}', delim=';', header=true)"
        ).fetchone()
        csv_count = row[0] if row else 0

        logger.info("CSV cadastral: %d linhas", csv_count)

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
                    nullstr  = ''
                )
            """)
            row = conn.execute("SELECT COUNT(*) FROM cad_cia_aberta_raw").fetchone()
            inserted = row[0] if row else 0

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

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

    row = conn.execute("SELECT COUNT(*) FROM b3_tickers").fetchone()
    count: int = row[0] if row else 0

    logger.info("Tickers B3 carregados: %d linhas em b3_tickers", count)
    return count
