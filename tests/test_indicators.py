"""Testes das funções puras e do orquestrador de indicadores (T027-T031)."""
from __future__ import annotations

from pathlib import Path

import pytest

from cvmdata.ingestion.db import init_indicators_schema, init_schema
from cvmdata.ingestion.loader import load_csv
from cvmdata.transform.account_map import ACCOUNT_MAP, get_component
from cvmdata.transform.indicators import (
    calculate_all,
    cobertura_juros,
    divida_bruta,
    divida_liquida,
    divida_liquida_pl,
    endividamento_geral,
    giro_ativo,
    liquidez_corrente,
    liquidez_geral,
    liquidez_imediata,
    liquidez_seca,
    margem_bruta,
    margem_liquida,
    margem_operacional,
    roa,
    roe,
)
from cvmdata.transform.normalize import normalize_table

# ── account_map ──────────────────────────────────────────────────────────────


def test_get_component_known():
    assert get_component("1") == "ativo_total"
    assert get_component("3.11") == "lucro_liquido"
    assert get_component("2.03") == "patrimonio_liquido"


def test_get_component_unknown_returns_none():
    assert get_component("9.99.99") is None


def test_account_map_has_expected_keys():
    expected = {
        "1", "1.01", "1.01.01", "1.01.02", "1.01.04",
        "1.02", "1.02.01",
        "2", "2.01", "2.01.04", "2.02", "2.02.01", "2.03",
        "3.01", "3.03", "3.05", "3.06.02", "3.11",
    }
    assert expected.issubset(set(ACCOUNT_MAP.keys()))


# ── Rentabilidade — casos felizes ─────────────────────────────────────────────


def test_roe_happy():
    assert roe(100, 500) == pytest.approx(20.0)


def test_roa_happy():
    assert roa(100, 2000) == pytest.approx(5.0)


def test_margem_bruta_happy():
    assert margem_bruta(300, 1000) == pytest.approx(30.0)


def test_margem_operacional_happy():
    assert margem_operacional(200, 1000) == pytest.approx(20.0)


def test_margem_liquida_happy():
    assert margem_liquida(150, 1000) == pytest.approx(15.0)


def test_giro_ativo_happy():
    assert giro_ativo(1000, 2000) == pytest.approx(0.5)


# ── Liquidez — casos felizes ──────────────────────────────────────────────────


def test_liquidez_corrente_happy():
    assert liquidez_corrente(200, 100) == pytest.approx(2.0)


def test_liquidez_seca_happy():
    assert liquidez_seca(200, 50, 100) == pytest.approx(1.5)


def test_liquidez_imediata_happy():
    assert liquidez_imediata(80, 100) == pytest.approx(0.8)


def test_liquidez_geral_happy():
    # (200 + 50) / (100 + 150) = 250 / 250 = 1.0
    assert liquidez_geral(200, 50, 100, 150) == pytest.approx(1.0)


# ── Endividamento — casos felizes ─────────────────────────────────────────────


def test_endividamento_geral_happy():
    assert endividamento_geral(100, 200, 1000) == pytest.approx(30.0)


def test_divida_bruta_happy():
    assert divida_bruta(300, 400) == pytest.approx(700.0)


def test_divida_liquida_happy():
    # (300+400) - 80 - 120 = 700 - 200 = 500
    assert divida_liquida(300, 400, 80, 120) == pytest.approx(500.0)


def test_divida_liquida_pl_happy():
    assert divida_liquida_pl(500, 1000) == pytest.approx(0.5)


def test_cobertura_juros_happy():
    assert cobertura_juros(200, 50) == pytest.approx(4.0)


# ── Denominador zero → None ───────────────────────────────────────────────────


@pytest.mark.parametrize("fn,args", [
    (roe,               (100, 0)),
    (roa,               (100, 0)),
    (margem_bruta,      (300, 0)),
    (margem_operacional,(200, 0)),
    (margem_liquida,    (150, 0)),
    (giro_ativo,        (1000, 0)),
    (liquidez_corrente, (200, 0)),
    (liquidez_seca,     (200, 50, 0)),
    (liquidez_imediata, (80, 0)),
    (liquidez_geral,    (200, 50, 0, 0)),
    (endividamento_geral,(100, 200, 0)),
    (divida_liquida_pl, (500, 0)),
    (cobertura_juros,   (200, 0)),
])
def test_zero_denominator_returns_none(fn, args):
    assert fn(*args) is None


# ── Argumento None → None ─────────────────────────────────────────────────────


@pytest.mark.parametrize("fn,args", [
    (roe,               (None, 500)),
    (roe,               (100, None)),
    (roa,               (None, 2000)),
    (margem_bruta,      (None, 1000)),
    (margem_operacional,(None, 1000)),
    (margem_liquida,    (None, 1000)),
    (giro_ativo,        (None, 2000)),
    (liquidez_corrente, (None, 100)),
    (liquidez_seca,     (None, 50, 100)),
    (liquidez_seca,     (200, None, 100)),
    (liquidez_imediata, (None, 100)),
    (liquidez_geral,    (None, 50, 100, 150)),
    (endividamento_geral,(None, 200, 1000)),
    (divida_bruta,      (None, 400)),
    (divida_liquida,    (None, 400, 80, 120)),
    (divida_liquida_pl, (None, 1000)),
    (cobertura_juros,   (None, 50)),
])
def test_none_argument_returns_none(fn, args):
    assert fn(*args) is None


# ── Integração: calculate_all ─────────────────────────────────────────────────

# Helpers para criar CSVs mínimos in-memory

def _bpa_csv(tmp_path, filename: str, rows: list[tuple[str, str, str, float]]) -> object:
    """Cria CSV de BPA/BPP com as linhas (cd_conta, ds_conta, dt_refer, vl_conta)."""
    header = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;"
        "MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"
    )
    lines = [header]
    cnpj = "00.000.000/0001-91"
    for cd_conta, ds, dt_refer, vl in rows:
        lines.append(
            f"{cnpj};{dt_refer};1;EMPRESA TEST;001000;DF Consolidado;"
            f"REAL;MIL;ÚLTIMO;{dt_refer};{cd_conta};{ds};{vl};S"
        )
    p = tmp_path / filename
    p.write_bytes("\n".join(lines).encode("latin1"))
    return p


def _dre_csv(tmp_path, filename: str, rows: list[tuple[str, str, str, float]]) -> object:
    """Cria CSV de DRE (15 colunas, com DT_INI_EXERC)."""
    header = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;"
        "MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;"
        "CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"
    )
    lines = [header]
    cnpj = "00.000.000/0001-91"
    for cd_conta, ds, dt_refer, vl in rows:
        lines.append(
            f"{cnpj};{dt_refer};1;EMPRESA TEST;001000;DF Consolidado;"
            f"REAL;MIL;ÚLTIMO;2024-01-01;{dt_refer};{cd_conta};{ds};{vl};S"
        )
    p = tmp_path / filename
    p.write_bytes("\n".join(lines).encode("latin1"))
    return p


DT = "2024-03-31"

BPA_ROWS = [
    ("1",       "Ativo Total",          DT, 10000.0),
    ("1.01",    "Ativo Circulante",     DT, 4000.0),
    ("1.01.01", "Caixa",                DT, 500.0),
    ("1.01.02", "Aplicações",           DT, 300.0),
    ("1.01.04", "Estoques",             DT, 200.0),
    ("1.02",    "Ativo Não Circ.",      DT, 6000.0),
    ("1.02.01", "Realizável LP",        DT, 800.0),
]
BPP_ROWS = [
    ("2",       "Passivo Total",        DT, 6000.0),
    ("2.01",    "Passivo Circulante",   DT, 2000.0),
    ("2.01.04", "Empréstimos CP",       DT, 600.0),
    ("2.02",    "Passivo Não Circ.",    DT, 3000.0),
    ("2.02.01", "Empréstimos LP",       DT, 1200.0),
    ("2.03",    "Patrimônio Líquido",   DT, 1000.0),
]
DRE_ROWS = [
    ("3.01",    "Receita Líquida",      DT, 5000.0),
    ("3.03",    "Resultado Bruto",      DT, 2000.0),
    ("3.05",    "EBIT",                 DT, 800.0),
    ("3.06.02", "Despesas Financeiras", DT, 200.0),
    ("3.11",    "Lucro Líquido",        DT, 500.0),
]


def test_calculate_all_inserts_15_indicators(tmp_path, db):
    """calculate_all deve gravar exatamente 15 indicadores por empresa/período."""
    init_schema(db)

    load_csv(db, _bpa_csv(tmp_path, "itr_cia_aberta_BPA_con_2024.csv", BPA_ROWS),
             "BPA", "itr", 2024, "con")
    load_csv(db, _bpa_csv(tmp_path, "itr_cia_aberta_BPP_con_2024.csv", BPP_ROWS),
             "BPP", "itr", 2024, "con")
    load_csv(db, _dre_csv(tmp_path, "itr_cia_aberta_DRE_con_2024.csv", DRE_ROWS),
             "DRE", "itr", 2024, "con")

    normalize_table("raw_bpa", db)
    normalize_table("raw_bpp", db)
    normalize_table("raw_dre", db)

    total = calculate_all(db)

    assert total == 15
    count = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count == 15


def test_calculate_all_roe_plausible(tmp_path, db):
    """ROE = 500/1000*100 = 50.0 com os dados de fixture."""
    init_schema(db)
    load_csv(db, _bpa_csv(tmp_path, "itr_cia_aberta_BPA_con_2024.csv", BPA_ROWS),
             "BPA", "itr", 2024, "con")
    load_csv(db, _bpa_csv(tmp_path, "itr_cia_aberta_BPP_con_2024.csv", BPP_ROWS),
             "BPP", "itr", 2024, "con")
    load_csv(db, _dre_csv(tmp_path, "itr_cia_aberta_DRE_con_2024.csv", DRE_ROWS),
             "DRE", "itr", 2024, "con")

    normalize_table("raw_bpa", db)
    normalize_table("raw_bpp", db)
    normalize_table("raw_dre", db)
    calculate_all(db)

    row = db.execute(
        "SELECT valor FROM indicators WHERE indicador = 'roe'"
    ).fetchone()
    assert row is not None
    assert row[0] == pytest.approx(50.0)


def test_calculate_all_cnpj_filter(tmp_path, db):
    """calculate_all com --cnpj deve processar apenas a empresa solicitada."""
    init_schema(db)
    load_csv(db, _bpa_csv(tmp_path, "itr_cia_aberta_BPA_con_2024.csv", BPA_ROWS),
             "BPA", "itr", 2024, "con")
    load_csv(db, _bpa_csv(tmp_path, "itr_cia_aberta_BPP_con_2024.csv", BPP_ROWS),
             "BPP", "itr", 2024, "con")
    load_csv(db, _dre_csv(tmp_path, "itr_cia_aberta_DRE_con_2024.csv", DRE_ROWS),
             "DRE", "itr", 2024, "con")
    normalize_table("raw_bpa", db)
    normalize_table("raw_bpp", db)
    normalize_table("raw_dre", db)

    total = calculate_all(db, cnpj="00.000.000/0001-91")
    assert total == 15

    # Filtrando cnpj inexistente → 0
    total_none = calculate_all(db, cnpj="99.999.999/0001-00")
    # A tabela indicators já tem 15 linhas da chamada anterior; nenhuma nova
    count_after = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count_after == 15
    assert total_none == 0


def test_calculate_all_idempotent(tmp_path, db):
    """Rodar calculate_all duas vezes não duplica registros em indicators."""
    init_schema(db)
    load_csv(db, _bpa_csv(tmp_path, "itr_cia_aberta_BPA_con_2024.csv", BPA_ROWS),
             "BPA", "itr", 2024, "con")
    load_csv(db, _bpa_csv(tmp_path, "itr_cia_aberta_BPP_con_2024.csv", BPP_ROWS),
             "BPP", "itr", 2024, "con")
    load_csv(db, _dre_csv(tmp_path, "itr_cia_aberta_DRE_con_2024.csv", DRE_ROWS),
             "DRE", "itr", 2024, "con")
    normalize_table("raw_bpa", db)
    normalize_table("raw_bpp", db)
    normalize_table("raw_dre", db)

    calculate_all(db)
    calculate_all(db)

    count = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count == 15


def test_calculate_all_empty_clean_tables(db):
    """Sem tabelas *_clean, calculate_all retorna 0 sem exception."""
    # Não chama init_schema — tabelas clean não existem
    # Deve avisar e retornar 0
    total = calculate_all(db)
    assert total == 0


# ── T029: Integração end-to-end com fixtures de BCO Brasil (setor banco) ──────

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_and_calc(db, bpa_path: Path, bpp_path: Path, dre_path: Path) -> None:
    """Helper: load → normalize → calculate_all (banco ou industrial)."""
    init_schema(db)
    load_csv(db, bpa_path, "BPA", "dfp", 2024, "con")
    load_csv(db, bpp_path, "BPP", "dfp", 2024, "con")
    load_csv(db, dre_path, "DRE", "dfp", 2024, "con")
    normalize_table("raw_bpa", db)
    normalize_table("raw_bpp", db)
    normalize_table("raw_dre", db)
    calculate_all(db)


def test_bank_integration_indicators_inserted(db):
    """Pipeline completo com fixtures de BCO Brasil: load→normalize→calculate."""
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_bank_bpa.csv",
        FIXTURES_DIR / "sample_bank_bpp.csv",
        FIXTURES_DIR / "sample_bank_dre.csv",
    )
    count = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count > 0


def test_bank_integration_roe_not_none(db):
    """ROE de BCO Brasil não é None — 3.11 (lucro) e 2.03 (PL/Provisões) presentes."""
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_bank_bpa.csv",
        FIXTURES_DIR / "sample_bank_bpp.csv",
        FIXTURES_DIR / "sample_bank_dre.csv",
    )
    row = db.execute(
        "SELECT valor FROM indicators WHERE indicador = 'roe'"
    ).fetchone()
    assert row is not None
    assert row[0] is not None


# ── T031: Testes multi-setor — industrial (PETROBRAS) + xfail banco ───────────


def test_industrial_all_15_indicators_inserted(db):
    """PETROBRAS: todas as 18 contas do ACCOUNT_MAP presentes → 15 indicadores."""
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_industrial_bpa.csv",
        FIXTURES_DIR / "sample_industrial_bpp.csv",
        FIXTURES_DIR / "sample_industrial_dre.csv",
    )
    count = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count == 15


def test_industrial_roe_not_none(db):
    """PETROBRAS: ROE calculado corretamente com 3.11 e 2.03 padrão."""
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_industrial_bpa.csv",
        FIXTURES_DIR / "sample_industrial_bpp.csv",
        FIXTURES_DIR / "sample_industrial_dre.csv",
    )
    row = db.execute(
        "SELECT valor FROM indicators WHERE indicador = 'roe'"
    ).fetchone()
    assert row is not None and row[0] is not None


def test_industrial_no_none_indicators(db):
    """PETROBRAS: nenhum dos 15 indicadores é None (todas as contas presentes)."""
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_industrial_bpa.csv",
        FIXTURES_DIR / "sample_industrial_bpp.csv",
        FIXTURES_DIR / "sample_industrial_dre.csv",
    )
    none_count = db.execute(
        "SELECT COUNT(*) FROM indicators WHERE valor IS NULL"
    ).fetchone()[0]
    assert none_count == 0


@pytest.mark.xfail(reason="sector_profile pending")
def test_bank_sector_liquidez_seca_not_none(db):
    """BCO Brasil: CD_CONTA 1.01.04 (Estoques) ausente no BPA de bancos.

    CD_CONTA esperado no ACCOUNT_MAP: 1.01.04 (Estoques)
    CD_CONTA encontrado no BPA de BCO Brasil: ausente (bancos não têm estoques)
    Impacto: estoques = None → liquidez_seca = None
    Correção futura: sector_profile para bancos mapeará componente alternativo.
    """
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_bank_bpa.csv",
        FIXTURES_DIR / "sample_bank_bpp.csv",
        FIXTURES_DIR / "sample_bank_dre.csv",
    )
    row = db.execute(
        "SELECT valor FROM indicators WHERE indicador = 'liquidez_seca'"
    ).fetchone()
    # xfail: banco não tem 1.01.04 → estoques = None → liquidez_seca = None
    assert row is not None and row[0] is not None


@pytest.mark.xfail(reason="sector_profile pending")
def test_bank_sector_divida_bruta_not_none(db):
    """BCO Brasil: CD_CONTA 2.01.04 (Empréstimos CP) ausente no BPP de bancos.

    CD_CONTA esperado no ACCOUNT_MAP: 2.01.04 (Empréstimos e Financiamentos CP)
    CD_CONTA encontrado no BPP de BCO Brasil: ausente
      (passivo circulante bancário não usa 2.01.04 — estrutura financeira COSIF)
    Impacto: emprestimos_cp = None → divida_bruta = None, divida_liquida = None
    Correção futura: sector_profile para bancos usará CD_CONTA alternativo.
    """
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_bank_bpa.csv",
        FIXTURES_DIR / "sample_bank_bpp.csv",
        FIXTURES_DIR / "sample_bank_dre.csv",
    )
    row = db.execute(
        "SELECT valor FROM indicators WHERE indicador = 'divida_bruta'"
    ).fetchone()
    # xfail: banco não tem 2.01.04 → emprestimos_cp = None → divida_bruta = None
    assert row is not None and row[0] is not None


# ── T033: US4 — Consulta de indicadores ──────────────────────────────────────

_QUERY_SQL = """
    SELECT cnpj_cia, dt_refer, indicador, valor
    FROM   indicators
    WHERE  cnpj_cia = ?
    ORDER BY dt_refer, indicador
"""

_SUMMARY_SQL = """
    SELECT cnpj_cia,
           COUNT(DISTINCT indicador) AS n_indicadores,
           MIN(dt_refer)             AS primeiro_periodo,
           MAX(dt_refer)             AS ultimo_periodo
    FROM   indicators
    GROUP BY cnpj_cia
    ORDER BY n_indicadores DESC
    LIMIT 10
"""


def _insert_indicators(db, rows: list[tuple]) -> None:
    """Insere linhas (cnpj_cia, dt_refer, indicador, valor) em indicators."""
    db.executemany(
        "INSERT OR REPLACE INTO indicators (cnpj_cia, dt_refer, indicador, valor) VALUES (?,?,?,?)",
        rows,
    )


def test_query_returns_records_for_cnpj(db):
    """Query com CNPJ retorna os registros conhecidos da tabela indicators."""
    init_indicators_schema(db)
    _insert_indicators(db, [
        ("11.111.111/0001-11", "2024-03-31", "roe", 20.0),
        ("11.111.111/0001-11", "2024-03-31", "roa", 10.0),
        ("22.222.222/0002-22", "2024-03-31", "roe", 5.0),
    ])

    rows = db.execute(_QUERY_SQL, ["11.111.111/0001-11"]).fetchall()

    assert len(rows) == 2
    assert rows[0][2] == "roa"   # ORDER BY indicador → roa antes de roe
    assert rows[1][2] == "roe"
    assert rows[0][3] == pytest.approx(10.0)
    assert rows[1][3] == pytest.approx(20.0)


def test_query_ordered_by_dt_refer(db):
    """Registros de múltiplos períodos devem estar ordenados por dt_refer ASC."""
    init_indicators_schema(db)
    _insert_indicators(db, [
        ("33.333.333/0003-33", "2024-09-30", "roe", 18.0),
        ("33.333.333/0003-33", "2024-03-31", "roe", 15.0),
        ("33.333.333/0003-33", "2024-06-30", "roe", 17.0),
    ])

    rows = db.execute(_QUERY_SQL, ["33.333.333/0003-33"]).fetchall()

    assert len(rows) == 3
    datas = [str(r[1]) for r in rows]
    assert datas == sorted(datas)


def test_query_unknown_cnpj_returns_empty(db):
    """CNPJ sem indicadores retorna lista vazia."""
    init_indicators_schema(db)
    rows = db.execute(_QUERY_SQL, ["99.999.999/0009-99"]).fetchall()
    assert rows == []


def test_query_summary_top10(db):
    """Sem filtro de CNPJ, resumo lista até 10 empresas ordenadas por n_indicadores DESC."""
    init_indicators_schema(db)
    _insert_indicators(db, [
        ("44.444.444/0001-44", "2024-03-31", "roe", 1.0),
        ("44.444.444/0001-44", "2024-03-31", "roa", 2.0),
        ("55.555.555/0001-55", "2024-03-31", "roe", 3.0),
    ])

    rows = db.execute(_SUMMARY_SQL).fetchall()

    assert len(rows) == 2
    # Empresa com 2 indicadores vem primeiro
    assert rows[0][0] == "44.444.444/0001-44"
    assert rows[0][1] == 2
    assert rows[1][0] == "55.555.555/0001-55"
    assert rows[1][1] == 1


def test_query_year_filter(db):
    """Filtro --year restringe resultados ao ano solicitado."""
    init_indicators_schema(db)
    _insert_indicators(db, [
        ("66.666.666/0001-66", "2023-12-31", "roe", 10.0),
        ("66.666.666/0001-66", "2024-03-31", "roe", 12.0),
        ("66.666.666/0001-66", "2024-06-30", "roe", 14.0),
    ])

    rows = db.execute(
        """
        SELECT cnpj_cia, dt_refer, indicador, valor
        FROM   indicators
        WHERE  cnpj_cia = ? AND YEAR(dt_refer) = ?
        ORDER BY dt_refer, indicador
        """,
        ["66.666.666/0001-66", 2024],
    ).fetchall()

    assert len(rows) == 2
    assert all(str(r[1]).startswith("2024") for r in rows)
