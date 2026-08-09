from __future__ import annotations

import json
from pathlib import Path

import duckdb

from cvmdata.ingestion.db import init_info_cad_schema, init_schema
from cvmdata.ingestion.loader import load_csv
from cvmdata.transform.normalize import normalize_table

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

DT = "2024-03-31"

BPA_ROWS = [
    ("1", "Ativo Total", DT, 10000.0),
    ("1.01", "Ativo Circulante", DT, 4000.0),
    ("1.01.01", "Caixa", DT, 500.0),
    ("1.01.02", "Aplicações", DT, 300.0),
    ("1.01.04", "Estoques", DT, 200.0),
    ("1.02", "Ativo Não Circ.", DT, 6000.0),
    ("1.02.01", "Realizável LP", DT, 800.0),
]
BPP_ROWS = [
    ("2", "Passivo Total", DT, 6000.0),
    ("2.01", "Passivo Circulante", DT, 2000.0),
    ("2.01.04", "Empréstimos CP", DT, 600.0),
    ("2.02", "Passivo Não Circ.", DT, 3000.0),
    ("2.02.01", "Empréstimos LP", DT, 1200.0),
    ("2.03", "Patrimônio Líquido", DT, 1000.0),
]
DRE_ROWS = [
    ("3.01", "Receita Líquida", DT, 5000.0),
    ("3.03", "Resultado Bruto", DT, 2000.0),
    ("3.05", "EBIT", DT, 800.0),
    ("3.06.02", "Despesas Financeiras", DT, 200.0),
    ("3.11", "Lucro Líquido", DT, 500.0),
]

_BALANCE_CODES = [
    "1",
    "1.01",
    "1.01.01",
    "1.01.02",
    "1.01.04",
    "1.02",
    "1.02.01",
    "2",
    "2.01",
    "2.01.04",
    "2.02",
    "2.02.01",
    "2.03",
]
_DRE_CODES = ["3.01", "3.03", "3.05", "3.06.02", "3.11"]


def make_balance_csv(
    path: Path,
    rows: int = 3,
    data_rows: list[tuple[str, str, str, float]] | None = None,
) -> Path:
    """Gera CSV no layout de balanço (14 cols, sem DT_INI_EXERC).

    Usado tanto para BPA quanto para BPP — ambos compartilham esse layout.
    """
    header = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;"
        "MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"
    )
    if data_rows is None:
        data_rows = []
        for index in range(rows):
            cd = _BALANCE_CODES[index % len(_BALANCE_CODES)]
            data_rows.append((cd, f"Conta {index}", DT, 1000 + index * 100.0))

    lines = [header]
    cnpj = "00.000.000/0001-91"
    for cd_conta, ds_conta, dt_refer, vl_conta in data_rows:
        lines.append(
            f"{cnpj};{dt_refer};1;EMPRESA TEST;001000;DF Consolidado;"
            f"REAL;MIL;ÚLTIMO;{dt_refer};{cd_conta};{ds_conta};{vl_conta};S"
        )
    path.write_bytes("\n".join(lines).encode("latin1"))
    return path


def make_flow_csv(
    path: Path,
    rows: int = 3,
    data_rows: list[tuple[str, str, str, float]] | None = None,
) -> Path:
    header = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;"
        "ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"
    )
    if data_rows is None:
        data_rows = []
        for index in range(rows):
            cd = _DRE_CODES[index % len(_DRE_CODES)]
            data_rows.append((cd, f"Conta {index}", DT, 1000 + index * 100.0))

    lines = [header]
    cnpj = "00.000.000/0001-91"
    for cd_conta, ds_conta, dt_refer, vl_conta in data_rows:
        lines.append(
            f"{cnpj};{dt_refer};1;EMPRESA TEST;001000;DF Consolidado;"
            f"REAL;MIL;ÚLTIMO;2024-01-01;{dt_refer};{cd_conta};{ds_conta};{vl_conta};S"
        )
    path.write_bytes("\n".join(lines).encode("latin1"))
    return path


def make_b3_tickers_json(path: Path) -> Path:
    payload = {
        "page": {
            "pageNumber": 1,
            "pageSize": 120,
            "totalRecords": 2,
            "totalPages": 1,
        },
        "results": [
            {
                "codeCVM": "1234",
                "issuingCompany": "ABCD",
                "companyName": "ABC COMPANHIA",
                "tradingName": "ABC",
                "cnpj": "12.345.678/0001-90",
                "status": "A",
                "segment": "Novo Mercado",
                "market": "Ações",
            },
            {
                "codeCVM": "9999",
                "issuingCompany": "WXYZ",
                "companyName": "WXYZ COMPANHIA",
                "tradingName": "WXYZ",
                "cnpj": "00.000.000/0001-00",
                "status": "I",
                "segment": "Tradicional",
                "market": "Ações",
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def make_cad_csv(path: Path, rows: list[dict]) -> Path:
    header = (
        "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;CD_CVM;SIT;DT_INI_SIT;"
        "TP_MERC;CATEG_REG;SETOR_ATIV;DT_INC"
    )
    lines = [header]
    for row in rows:
        lines.append(
            f"{row.get('CNPJ_CIA', '00.000.000/0001-91')};"
            f"{row.get('DENOM_SOCIAL', 'CIA TESTE')};"
            f"{row.get('DENOM_COMERC', '')};"
            f"{row.get('CD_CVM', '001')};"
            f"{row.get('SIT', 'ATIVO')};"
            f"{row.get('DT_INI_SIT', '2020-01-01')};"
            f"{row.get('TP_MERC', 'BOLSA')};"
            f"{row.get('CATEG_REG', 'A')};"
            f"{row.get('SETOR_ATIV', '')};"
            f"{row.get('DT_INC', '2020-01-01')}"
        )
    path.write_bytes("\n".join(lines).encode("latin-1"))
    return path


def setup_classify_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cad_cia_aberta_raw (
            CNPJ_CIA     VARCHAR,
            DENOM_SOCIAL VARCHAR,
            DENOM_COMERC VARCHAR,
            CD_CVM       VARCHAR,
            SIT          VARCHAR,
            DT_INI_SIT   VARCHAR,
            TP_MERC      VARCHAR,
            CATEG_REG    VARCHAR,
            SETOR_ATIV   VARCHAR,
            DT_INC       VARCHAR,
            loaded_at    TIMESTAMPTZ
        )
        """
    )
    init_info_cad_schema(conn)


def prepare_indicator_pipeline(
    conn: duckdb.DuckDBPyConnection,
    tmp_path: Path,
    *,
    source: str,
    year: int,
    bpa_rows: list[tuple[str, str, str, float]] | None = None,
    bpp_rows: list[tuple[str, str, str, float]] | None = None,
    dre_rows: list[tuple[str, str, str, float]] | None = None,
) -> None:
    if bpa_rows is None:
        bpa_rows = BPA_ROWS
    if bpp_rows is None:
        bpp_rows = BPP_ROWS
    if dre_rows is None:
        dre_rows = DRE_ROWS

    init_schema(conn)
    load_csv(
        conn,
        make_balance_csv(tmp_path / f"{source}_cia_aberta_BPA_con_{year}.csv", data_rows=bpa_rows),
        "BPA",
        source,
        year,
        "con",
    )
    load_csv(
        conn,
        make_balance_csv(tmp_path / f"{source}_cia_aberta_BPP_con_{year}.csv", data_rows=bpp_rows),
        "BPP",
        source,
        year,
        "con",
    )
    load_csv(
        conn,
        make_flow_csv(tmp_path / f"{source}_cia_aberta_DRE_con_{year}.csv", data_rows=dre_rows),
        "DRE",
        source,
        year,
        "con",
    )
    normalize_table("raw_bpa", conn)
    normalize_table("raw_bpp", conn)
    normalize_table("raw_dre", conn)


def seed_classification_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict],
) -> None:
    setup_classify_schema(conn)
    insert_raw_cad(conn, rows)


def insert_raw_cad(conn: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    for row in rows:
        conn.execute(
            """
            INSERT INTO cad_cia_aberta_raw
                (CNPJ_CIA, DENOM_SOCIAL, DENOM_COMERC, CD_CVM, SIT, DT_INI_SIT,
                 TP_MERC, CATEG_REG, SETOR_ATIV, DT_INC, loaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            [
                row.get("CNPJ_CIA", "00.000.000/0001-91"),
                row.get("DENOM_SOCIAL", "CIA TESTE"),
                row.get("DENOM_COMERC", ""),
                row.get("CD_CVM", "001"),
                row.get("SIT", "ATIVO"),
                row.get("DT_INI_SIT", "2020-01-01"),
                row.get("TP_MERC", "BOLSA"),
                row.get("CATEG_REG", "A"),
                row.get("SETOR_ATIV", ""),
                row.get("DT_INC", "2020-01-01"),
            ],
        )


def insert_raw_bpa(
    conn: duckdb.DuckDBPyConnection,
    *,
    cnpj: str = "33.000.167/0001-01",
    dt_refer: str = "2024-09-30",
    cd_conta: str = "1",
    ds_conta: str = "Ativo Total",
    vl_conta: float = 10000.0,
) -> None:
    """Insere linha em raw_bpa (17 colunas do schema BALANCE) para testes."""
    conn.execute(
        """
        INSERT INTO raw_bpa VALUES (
            ?, ?, 1, 'EMPRESA TEST', '33000167',
            'DF Consolidado - BPA', 'REAL', 'MIL',
            'ÚLTIMO', ?, ?, ?, ?, 'S',
            'itr', 2024, 'con'
        )
        """,
        [cnpj, dt_refer, dt_refer, cd_conta, ds_conta, vl_conta],
    )


def insert_raw_bpp(
    conn: duckdb.DuckDBPyConnection,
    *,
    cnpj: str = "33.000.167/0001-01",
    dt_refer: str = "2024-09-30",
    cd_conta: str = "2.03",
    ds_conta: str = "Patrimônio Líquido",
    vl_conta: float = 1000.0,
) -> None:
    """Insere linha em raw_bpp (17 colunas do schema BALANCE) para testes."""
    conn.execute(
        """
        INSERT INTO raw_bpp VALUES (
            ?, ?, 1, 'EMPRESA TEST', '33000167',
            'DF Consolidado - BPP', 'REAL', 'MIL',
            'ÚLTIMO', ?, ?, ?, ?, 'S',
            'itr', 2024, 'con'
        )
        """,
        [cnpj, dt_refer, dt_refer, cd_conta, ds_conta, vl_conta],
    )


def insert_raw_dre(
    conn: duckdb.DuckDBPyConnection,
    *,
    cnpj: str = "33.000.167/0001-01",
    dt_refer: str = "2024-09-30",
    versao: int = 1,
    cd_conta: str = "3.01",
    ds_conta: str = "Conta Teste",
    vl_conta: float = 369.0,
    ordem_exerc: str = "ÚLTIMO",
    dt_ini_exerc: str = "2024-01-01",
    dt_fim_exerc: str = "2024-09-30",
    cd_cvm: str = "009512",
    source: str = "itr",
    escala_moeda: str = "UNIDADE",
) -> None:
    """Insere linha em raw_dre (18 colunas do schema DRE) para testes de TTM."""
    conn.execute(
        """
        INSERT INTO raw_dre VALUES (
            ?, ?, ?, 'EMPRESA TEST', ?,
            'DF Consolidado - DRE', 'REAL', ?,
            ?, ?, ?,
            ?, ?, ?, 'S',
            ?, 2024, 'con'
        )
        """,
        [
            cnpj,
            dt_refer,
            versao,
            cd_cvm,
            escala_moeda,
            ordem_exerc,
            dt_ini_exerc,
            dt_fim_exerc,
            cd_conta,
            ds_conta,
            vl_conta,
            source,
        ],
    )
