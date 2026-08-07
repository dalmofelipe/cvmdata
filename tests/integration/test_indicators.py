"""Testes de integração de indicadores."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvmdata.ingestion.db import init_schema
from cvmdata.ingestion.loader import load_csv
from cvmdata.transform.indicators import _get_ttm_value, calculate_all
from cvmdata.transform.normalize import normalize_table
from tests.support import (
    FIXTURES_DIR,
    insert_raw_bpa,
    insert_raw_bpp,
    insert_raw_dre,
    prepare_indicator_pipeline,
)

pytestmark = pytest.mark.integration


# ── Integração: calculate_all ─────────────────────────────────────────────────


def test_calculate_all_inserts_15_indicators(tmp_path: Path, db):
    """calculate_all deve gravar exatamente 15 indicadores por empresa/período."""
    prepare_indicator_pipeline(db, tmp_path, source="itr", year=2024)
    total = calculate_all(db)

    assert total == 15
    count = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count == 15


def test_calculate_all_roe_plausible(tmp_path: Path, db):
    """ROE = 500/1000*100 = 50.0 com os dados de fixture."""
    prepare_indicator_pipeline(db, tmp_path, source="itr", year=2024)
    calculate_all(db)

    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'roe'").fetchone()
    assert row is not None
    assert row[0] == pytest.approx(50.0)


def test_calculate_all_cnpj_filter(tmp_path: Path, db):
    """calculate_all com --cnpj deve processar apenas a empresa solicitada."""
    prepare_indicator_pipeline(db, tmp_path, source="itr", year=2024)

    total = calculate_all(db, cnpj="00.000.000/0001-91")
    assert total == 15

    # Filtrando cnpj inexistente → 0
    total_none = calculate_all(db, cnpj="99.999.999/0001-00")
    # A tabela indicators já tem 15 linhas da chamada anterior; nenhuma nova
    count_after = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count_after == 15
    assert total_none == 0



def test_calculate_all_idempotent(tmp_path: Path, db):
    """Rodar calculate_all duas vezes não duplica registros em indicators."""
    prepare_indicator_pipeline(db, tmp_path, source="itr", year=2024)

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
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'roe'").fetchone()
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
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'roe'").fetchone()
    assert row is not None and row[0] is not None


def test_industrial_no_none_indicators(db):
    """PETROBRAS: nenhum dos 15 indicadores é None (todas as contas presentes)."""
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_industrial_bpa.csv",
        FIXTURES_DIR / "sample_industrial_bpp.csv",
        FIXTURES_DIR / "sample_industrial_dre.csv",
    )
    none_count = db.execute("SELECT COUNT(*) FROM indicators WHERE valor IS NULL").fetchone()[0]
    assert none_count == 0


@pytest.mark.xfail(reason="sector_profile pending", strict=True)
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
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'liquidez_seca'").fetchone()
    # xfail: banco não tem 1.01.04 → estoques = None → liquidez_seca = None
    assert row is not None and row[0] is not None


@pytest.mark.xfail(reason="sector_profile pending", strict=True)
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
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'divida_bruta'").fetchone()
    # xfail: banco não tem 2.01.04 → emprestimos_cp = None → divida_bruta = None
    assert row is not None and row[0] is not None


# ── Helpers para testes TTM ───────────────────────────────────────────────────

_TTM_CNPJ = "33.000.167/0001-01"  # Petrobras-like CNPJ para testes TTM


# ── T015: TTM completo ────────────────────────────────────────────────────────


def test_ttm_full(db):
    """T015 — YTD=369, FY=494, YTD_ant=377 → TTM = 369 + (494-377) = 486."""
    init_schema(db)
    # ITR Q3/2024 — ÚLTIMO (YTD janeiro-setembro)
    insert_raw_dre(
        db,
        dt_refer="2024-09-30",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2024-01-01",
        dt_fim_exerc="2024-09-30",
        vl_conta=369.0,
    )
    # ITR Q3/2024 — PENÚLTIMO (YTD ano anterior, mesmo período)
    insert_raw_dre(
        db,
        dt_refer="2024-09-30",
        ordem_exerc="PENÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2024-09-30",
        vl_conta=377.0,
    )
    # DFP FY2023 — ÚLTIMO (ano completo)
    insert_raw_dre(
        db,
        dt_refer="2023-12-31",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2023-12-31",
        vl_conta=494.0,
        source="dfp",
    )

    normalize_table("raw_dre", db)

    result = _get_ttm_value(db, _TTM_CNPJ, "2024-09-30", "3.01")

    assert result == pytest.approx(486.0)  # 369 + (494 - 377)


# ── T016: Fallback sem PENÚLTIMO ──────────────────────────────────────────────


def test_ttm_fallback_no_penultimo(db):
    """T016 — Sem PENÚLTIMO → retorna FY direto (494)."""
    init_schema(db)
    insert_raw_dre(
        db,
        dt_refer="2024-09-30",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2024-01-01",
        dt_fim_exerc="2024-09-30",
        vl_conta=369.0,
    )
    insert_raw_dre(
        db,
        dt_refer="2023-12-31",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2023-12-31",
        vl_conta=494.0,
        source="dfp",
    )

    normalize_table("raw_dre", db)

    result = _get_ttm_value(db, _TTM_CNPJ, "2024-09-30", "3.01")

    assert result == pytest.approx(494.0)


# ── T017: Fallback sem DFP anterior ──────────────────────────────────────────


def test_ttm_fallback_no_dfp(db):
    """T017 — Sem DFP anterior → retorna YTD parcial (369)."""
    init_schema(db)
    insert_raw_dre(
        db,
        dt_refer="2024-09-30",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2024-01-01",
        dt_fim_exerc="2024-09-30",
        vl_conta=369.0,
    )
    insert_raw_dre(
        db,
        dt_refer="2024-09-30",
        ordem_exerc="PENÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2024-09-30",
        vl_conta=377.0,
    )
    # Sem DFP

    normalize_table("raw_dre", db)

    result = _get_ttm_value(db, _TTM_CNPJ, "2024-09-30", "3.01")

    assert result == pytest.approx(369.0)


# ── T018: Fallback sem ITR (só DFP) ──────────────────────────────────────────


def test_ttm_fallback_no_itr(db):
    """T018 — Consulta a um dt_refer sem NENHUMA linha na base → None.

    Diferente dos demais fallbacks (que tratam ausência de PENÚLTIMO ou de
    DFP anterior para um período que EXISTE nos dados), este caso consulta
    um dt_refer para o qual a empresa não reportou nada — nem ITR nem DFP
    diretamente nessa data. Não há "TTM hipotético" a calcular: o
    pipeline de produção (_fetch_all_dre_components) nunca gera um
    indicador para um período sem nenhuma linha ÚLTIMO na base, então
    _get_ttm_value — que é um wrapper sobre a mesma fonte de verdade —
    reproduz o mesmo comportamento.
    """
    init_schema(db)
    insert_raw_dre(
        db,
        dt_refer="2023-12-31",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2023-12-31",
        vl_conta=494.0,
        source="dfp",
    )

    normalize_table("raw_dre", db)

    # Consulta para dt_refer que não tem nenhuma linha registrada
    result = _get_ttm_value(db, _TTM_CNPJ, "2024-09-30", "3.01")

    assert result is None


# ── T019: Ano fiscal não-dezembro ─────────────────────────────────────────────


def test_ttm_non_december_fiscal_year(db):
    """T019 — Empresa com fiscal year abril-março: DFP em março localizado corretamente."""
    init_schema(db)
    # DFP FY2024 terminando em março (ano fiscal abril-março)
    insert_raw_dre(
        db,
        dt_refer="2024-03-31",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2023-04-01",
        dt_fim_exerc="2024-03-31",
        vl_conta=300.0,
        source="dfp",
    )
    # ITR Q1 (abril-junho 2024) — ÚLTIMO (YTD desde abril)
    insert_raw_dre(
        db,
        dt_refer="2024-06-30",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2024-04-01",
        dt_fim_exerc="2024-06-30",
        vl_conta=80.0,
    )
    # ITR Q1 — PENÚLTIMO (YTD mesmo período ano anterior)
    insert_raw_dre(
        db,
        dt_refer="2024-06-30",
        ordem_exerc="PENÚLTIMO",
        dt_ini_exerc="2023-04-01",
        dt_fim_exerc="2024-06-30",
        vl_conta=70.0,
    )

    normalize_table("raw_dre", db)

    result = _get_ttm_value(db, _TTM_CNPJ, "2024-06-30", "3.01")

    # TTM = 80 + (300 - 70) = 310
    assert result == pytest.approx(310.0)


# ── T019b: Dois DFPs — seleciona o FY correto ───────────────────────────────


def test_ttm_two_dfps_selects_correct_fy(db):
    """T019b — Dois DFPs (FY2022 e FY2023) → seleciona FY2023 para ITR Q3/2024."""
    init_schema(db)
    # DFP FY2022
    insert_raw_dre(
        db,
        dt_refer="2022-12-31",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2022-01-01",
        dt_fim_exerc="2022-12-31",
        vl_conta=400.0,
        source="dfp",
        versao=1,
    )
    # DFP FY2023
    insert_raw_dre(
        db,
        dt_refer="2023-12-31",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2023-12-31",
        vl_conta=494.0,
        source="dfp",
        versao=1,
    )
    # ITR Q3/2024 — ÚLTIMO
    insert_raw_dre(
        db,
        dt_refer="2024-09-30",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2024-01-01",
        dt_fim_exerc="2024-09-30",
        vl_conta=369.0,
    )
    # ITR Q3/2024 — PENÚLTIMO
    insert_raw_dre(
        db,
        dt_refer="2024-09-30",
        ordem_exerc="PENÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2024-09-30",
        vl_conta=377.0,
    )

    normalize_table("raw_dre", db)

    result = _get_ttm_value(db, _TTM_CNPJ, "2024-09-30", "3.01")

    # FY2023 (494) should win over FY2022 (400)
    # TTM = 369 + (494 - 377) = 486
    assert result == pytest.approx(486.0)


# ── T025: Regressão batch — calculate_all com múltiplas empresas ─────────────


def test_calculate_all_regression_batch(tmp_path: Path, db):
    """T025 — calculate_all produz indicadores corretos via batch (vs. comportamento esperado).

    Usa fixture com BPA/BPP+DRE ITR, confirma que os indicadores de resultado
    (margem_liquida, roe) são calculados com TTM quando possível, ou YTD quando
    não há DFP anterior (fixture sem DFP → fallback para YTD).
    """
    prepare_indicator_pipeline(db, tmp_path, source="itr", year=2024)

    total = calculate_all(db)

    assert total == 15
    # Sem DFP → fallback YTD; margem_liquida = 500/5000*100 = 10.0
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'margem_liquida'").fetchone()
    assert row is not None
    assert row[0] == pytest.approx(10.0)
    # ROE = 500/1000*100 = 50.0
    roe_row = db.execute("SELECT valor FROM indicators WHERE indicador = 'roe'").fetchone()
    assert roe_row[0] == pytest.approx(50.0)


# ── T027: Integration test: batch TTM correctness via calculate_all ──────────

def test_calculate_all_ttm_correctness(db):
    """T027 — calculate_all (batch path) produces correct TTM values.

    Sets up the same TTM scenario as test_ttm_full:
    - ITR Q3/2024 ÚLTIMO (YTD): 369
    - ITR Q3/2024 PENÚLTIMO (YTD-1): 377
    - DFP FY2023 (full year): 494

    Expected TTM = 369 + (494 - 377) = 486

    This test validates that _fetch_all_dre_components and calculate_all
    produce the same result as the unit test oracle (_get_ttm_value).
    """
    init_schema(db)

    insert_raw_dre(
        db,
        cnpj=_TTM_CNPJ,
        dt_refer="2024-09-30",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2024-01-01",
        dt_fim_exerc="2024-09-30",
        cd_conta="3.01",
        vl_conta=369.0,
        escala_moeda="MIL",
    )
    insert_raw_dre(
        db,
        cnpj=_TTM_CNPJ,
        dt_refer="2024-09-30",
        ordem_exerc="PENÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2024-09-30",
        cd_conta="3.01",
        vl_conta=377.0,
        escala_moeda="MIL",
    )
    insert_raw_dre(
        db,
        cnpj=_TTM_CNPJ,
        dt_refer="2023-12-31",
        ordem_exerc="ÚLTIMO",
        dt_ini_exerc="2023-01-01",
        dt_fim_exerc="2023-12-31",
        cd_conta="3.01",
        vl_conta=494.0,
        source="dfp",
        escala_moeda="MIL",
    )

    insert_raw_bpa(db, cnpj=_TTM_CNPJ, cd_conta="1", ds_conta="Ativo Total", vl_conta=10000.0)
    insert_raw_bpa(
        db,
        cnpj=_TTM_CNPJ,
        cd_conta="1.01",
        ds_conta="Ativo Circulante",
        vl_conta=4000.0,
    )
    insert_raw_bpa(db, cnpj=_TTM_CNPJ, cd_conta="1.02", ds_conta="Ativo Não Circ", vl_conta=6000.0)
    insert_raw_bpp(
        db,
        cnpj=_TTM_CNPJ,
        cd_conta="2.03",
        ds_conta="Patrimônio Líquido",
        vl_conta=1000.0,
    )
    insert_raw_dre(
        db,
        cnpj=_TTM_CNPJ,
        cd_conta="3.11",
        ds_conta="Lucro Líquido",
        vl_conta=500.0,
        escala_moeda="MIL",
    )

    normalize_table("raw_bpa", db)
    normalize_table("raw_bpp", db)
    normalize_table("raw_dre", db)

    total = calculate_all(db)

    assert total > 0

    rows = dict(
        db.execute(
            f"""
            SELECT indicador, valor FROM indicators
            WHERE cnpj_cia = '{_TTM_CNPJ}' AND dt_refer = '2024-09-30'
            """
        ).fetchall()
    )

    # ROE = lucro_líquido / PL = 500 / 1000 * 100 = 50.0
    assert rows["roe"] == pytest.approx(50.0)
    # receita_liquida (3.01) entra via TTM = 369 + (494 - 377) = 486
    # margem_liquida = lucro_líquido (500) / receita_liquida (486) * 100
    assert rows["margem_liquida"] == pytest.approx(500 / 486 * 100)
