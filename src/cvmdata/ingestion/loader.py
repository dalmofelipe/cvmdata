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

from cvmdata.ingestion.db import BALANCE_DEMOS, DEMOS, FLOW_DEMOS, init_schema
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


def _build_insert_sql(csv_path: Path, demo: str, source: str, year: int, scope: str) -> str:
    """Monta o SQL de INSERT conforme o grupo de schema do demonstrativo.

    Filtra apenas as linhas cujo CD_CONTA está no ACCOUNT_MAP, descartando
    todas as contas irrelevantes para os indicadores antes da persistência.
    """
    table = f"raw_{demo.lower()}"
    demo_upper = demo.upper()
    fpath = csv_path.as_posix()

    if demo_upper in BALANCE_DEMOS:
        # 14 colunas — BPA, BPP (sem DT_INI_EXERC)
        data_select = """\
        CNPJ_CIA::VARCHAR,
        CAST(DT_REFER AS DATE),
        VERSAO::SMALLINT,
        DENOM_CIA::VARCHAR,
        CD_CVM::VARCHAR,
        GRUPO_DFP::VARCHAR,
        MOEDA::VARCHAR,
        ESCALA_MOEDA::VARCHAR,
        ORDEM_EXERC::VARCHAR,
        CAST(DT_FIM_EXERC AS DATE),
        CD_CONTA::VARCHAR,
        DS_CONTA::VARCHAR,
        TRY_CAST(VL_CONTA AS DOUBLE),
        ST_CONTA_FIXA::VARCHAR"""
    elif demo_upper in FLOW_DEMOS:
        # 15 colunas — DRE (com DT_INI_EXERC)
        data_select = """\
        CNPJ_CIA::VARCHAR,
        CAST(DT_REFER AS DATE),
        VERSAO::SMALLINT,
        DENOM_CIA::VARCHAR,
        CD_CVM::VARCHAR,
        GRUPO_DFP::VARCHAR,
        MOEDA::VARCHAR,
        ESCALA_MOEDA::VARCHAR,
        ORDEM_EXERC::VARCHAR,
        CAST(DT_INI_EXERC AS DATE),
        CAST(DT_FIM_EXERC AS DATE),
        CD_CONTA::VARCHAR,
        DS_CONTA::VARCHAR,
        TRY_CAST(VL_CONTA AS DOUBLE),
        ST_CONTA_FIXA::VARCHAR"""
    else:
        # 16 colunas — DMPL (com DT_INI_EXERC + COLUNA_DF)
        data_select = """\
        CNPJ_CIA::VARCHAR,
        CAST(DT_REFER AS DATE),
        VERSAO::SMALLINT,
        DENOM_CIA::VARCHAR,
        CD_CVM::VARCHAR,
        GRUPO_DFP::VARCHAR,
        MOEDA::VARCHAR,
        ESCALA_MOEDA::VARCHAR,
        ORDEM_EXERC::VARCHAR,
        CAST(DT_INI_EXERC AS DATE),
        CAST(DT_FIM_EXERC AS DATE),
        COLUNA_DF::VARCHAR,
        CD_CONTA::VARCHAR,
        DS_CONTA::VARCHAR,
        TRY_CAST(VL_CONTA AS DOUBLE),
        ST_CONTA_FIXA::VARCHAR"""

    return f"""
INSERT INTO {table}
SELECT
{data_select},
        '{source}'::VARCHAR  AS source,
        {year}::SMALLINT     AS year,
        '{scope}'::VARCHAR   AS scope
FROM read_csv(
    '{fpath}',
    delim    = ';',
    header   = true,
    encoding = 'latin-1',
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
    if demo not in DEMOS:
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

    Escaneia raw_dir/{source}/{year}/*.csv, identifica demos via filename e
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
