"""Testes de integração de indicadores."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvmdata.ingestion.database import init_schema
from cvmdata.ingestion.loader import load_csv
from cvmdata.transform.calc_plan import EXPECTED_INDICATOR_COUNT
from cvmdata.transform.indicators import _get_ttm_value, calculate_all
from cvmdata.transform.indicators.balance import fetch_all_balance_components
from cvmdata.transform.info_cad import classify_info_cad
from cvmdata.transform.normalize import normalize_table
from cvmdata.transform.profile import fetch_profiles_from_classification
from tests.support import (
    FIXTURES_DIR,
    insert_raw_bpa,
    insert_raw_bpp,
    insert_raw_dre,
    prepare_indicator_pipeline,
    setup_classify_schema,
)

pytestmark = pytest.mark.integration


# ── Integração: calculate_all ─────────────────────────────────────────────────


def test_calculate_all_inserts_indicators(tmp_path: Path, db):
    """calculate_all deve gravar exatamente EXPECTED_INDICATOR_COUNT por empresa/período."""
    prepare_indicator_pipeline(db, tmp_path, source="itr", year=2024)
    total = calculate_all(db)

    assert total == EXPECTED_INDICATOR_COUNT
    count = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count == EXPECTED_INDICATOR_COUNT


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
    assert total == EXPECTED_INDICATOR_COUNT

    # Filtrando cnpj inexistente → 0
    total_none = calculate_all(db, cnpj="99.999.999/0001-00")
    # A tabela indicators já tem EXPECTED_INDICATOR_COUNT linhas da chamada
    # anterior; nenhuma nova
    count_after = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count_after == EXPECTED_INDICATOR_COUNT
    assert total_none == 0



def test_calculate_all_idempotent(tmp_path: Path, db):
    """Rodar calculate_all duas vezes não duplica registros em indicators."""
    prepare_indicator_pipeline(db, tmp_path, source="itr", year=2024)

    calculate_all(db)
    calculate_all(db)

    count = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count == EXPECTED_INDICATOR_COUNT


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


# ── Inter: ausente do cadastro → heurística estrutural (design 3.4) ──────────


def _load_bank_only(db) -> None:
    """Helper: init_schema + load/normalize apenas das fixtures bancárias."""
    init_schema(db)
    load_csv(db, FIXTURES_DIR / "sample_bank_bpa.csv", "BPA", "dfp", 2024, "con")
    load_csv(db, FIXTURES_DIR / "sample_bank_bpp.csv", "BPP", "dfp", 2024, "con")
    load_csv(db, FIXTURES_DIR / "sample_bank_dre.csv", "DRE", "dfp", 2024, "con")
    normalize_table("raw_bpa", db)
    normalize_table("raw_bpp", db)
    normalize_table("raw_dre", db)


def test_structural_classification_persists_bank_fixture_without_info_cad(db):
    """CNPJ ausente do cadastro com assinatura BPA '1.01' → banking persistido.

    O step de classificação cadastral (pós-normalize) persiste o perfil
    estrutural em ``company_classification``; o fetch de balanço passa a
    consumir o perfil persistido (2.07 → patrimonio_liquido, não 2.03).
    """
    setup_classify_schema(db)
    _load_bank_only(db)

    classify_info_cad(db)

    row = db.execute(
        "SELECT profile_id, confidence FROM company_classification WHERE cnpj_cia = ?",
        ["00.000.000/0001-91"],
    ).fetchone()
    assert row == ("banking", "medium")

    event = db.execute(
        "SELECT event_type FROM classification_curation_events WHERE cnpj_cia = ?",
        ["00.000.000/0001-91"],
    ).fetchone()
    assert event is not None
    assert event[0] == "missing_from_cadastro"

    profiles = fetch_profiles_from_classification(db)
    assert profiles == {"00.000.000/0001-91": "banking"}

    comps = fetch_all_balance_components(db, None, profiles)
    (cnpj_dt,) = comps.keys()
    assert comps[cnpj_dt]["patrimonio_liquido"] == 150000000000.0
    assert "provisoes" not in comps[cnpj_dt]


def test_structural_heuristic_ignores_cnpjs_present_in_cadastro(db):
    """CNPJ no cadastro (mesmo não classificado) não recebe classificação estrutural."""
    setup_classify_schema(db)
    _load_bank_only(db)

    # CNPJ presente no cadastro com SIT=CANCELADA (não-classificável → default)
    db.execute(
        """
        INSERT INTO cad_cia_aberta_raw
            (CNPJ_CIA, DENOM_SOCIAL, DENOM_COMERC, CD_CVM, SIT, DT_INI_SIT,
             TP_MERC, CATEG_REG, SETOR_ATIV, DT_INC, loaded_at)
        VALUES ('00.000.000/0001-91', 'BCO TEST', '', '001', 'CANCELADA',
                '2020-01-01', 'BOLSA', 'A', '', '2020-01-01', current_timestamp)
        """
    )

    classify_info_cad(db)

    # Presente no cadastro → sem classificação (setor) nem estrutural
    assert db.execute("SELECT COUNT(*) FROM company_classification").fetchone()[0] == 0
    profiles = fetch_profiles_from_classification(db)
    assert profiles == {}

    comps = fetch_all_balance_components(db, None, profiles)
    # Mapeamento default: 2.03 (provisões) vira patrimonio_liquido; 2.07 é ignorada
    (cnpj_dt,) = comps.keys()
    assert comps[cnpj_dt]["patrimonio_liquido"] == 26099013000.0


def test_inter_end_to_end_structural_banking(db, tmp_path: Path):
    """Caso Inter: CNPJ ausente do cadastro → banking estrutural de ponta a ponta.

    Cadastro vazio (cad_cia_aberta_raw existe mas não tem o CNPJ) → a
    classificação setorial não o cobre; a assinatura BPA '1.01' dispara a
    classificação estrutural, que é PERSISTIDA em ``company_classification``
    com confidence='medium' + evento de curadoria ``missing_from_cadastro``.
    O cálculo consome o perfil persistido.
    """
    setup_classify_schema(db)
    _load_bank_only(db)

    classify_info_cad(db)

    row = db.execute(
        "SELECT profile_id, confidence, rule_applied FROM company_classification"
        " WHERE cnpj_cia = ?",
        ["00.000.000/0001-91"],
    ).fetchone()
    assert row[0] == "banking"
    assert row[1] == "medium"
    assert "structural_heuristic" in row[2]

    calculate_all(db)

    # ROE = lucro(3.11)/PL(2.07) = 19171564000/150000000000*100 ≈ 12.781
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'roe'").fetchone()
    assert row is not None
    assert row[0] == pytest.approx(19171564000 / 150000000000 * 100, abs=1e-4)

    # Taxa efetiva pela cauda (3.05 pré-tributos / 3.06 IR) → ~30.82%.
    # taxa_efetiva_ir não é mais indicador publicado — verificada via função
    # pura sobre os componentes (Item 1 da rodada 2).
    from cvmdata.transform.calc_plan import taxa_efetiva_ir
    from cvmdata.transform.indicators.calculate_all import _collect_components

    tables = {"raw_bpa_clean", "raw_bpp_clean", "raw_dre_clean"}
    comps = _collect_components(db, "00.000.000/0001-91", tables)
    assert len(comps) == 1
    comp = next(iter(comps.values()))
    taxa = taxa_efetiva_ir(
        comp["imposto_renda_csll"], comp["resultado_antes_tributos"]
    )
    assert taxa == pytest.approx(8539025000 / 27710589000, abs=1e-4)
    assert taxa > 0.0

    # Sem EBIT em banking → ROIC não computável (INDICATOR_POLICY)
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'roic'").fetchone()
    assert row is not None and row[0] is None


def test_collect_components_computes_lucro_liquido_final(tmp_path: Path, db):
    """Componente interno: continuadas + descontinuadas → lucro_liquido_final."""
    from cvmdata.transform.indicators.calculate_all import _collect_components

    prepare_indicator_pipeline(db, tmp_path, source="itr", year=2024)
    insert_raw_dre(
        db,
        cd_conta="3.10",
        ds_conta="Resultado Líquido das Operações Continuadas",
        vl_conta=450.0,
        dt_fim_exerc="2024-03-31",
    )
    insert_raw_dre(
        db,
        cd_conta="3.10.01",
        ds_conta="Resultado Líquido de Operações Descontinuadas",
        vl_conta=50.0,
        dt_fim_exerc="2024-03-31",
    )
    normalize_table("raw_dre", db)

    tables = {"raw_bpa_clean", "raw_bpp_clean", "raw_dre_clean"}
    comps = _collect_components(db, None, tables)

    keys = {k for k, comp in comps.items() if comp.get("resultado_liquido_continuadas")}
    assert keys
    key = sorted(keys)[0]
    assert comps[key]["lucro_liquido_final"] == 500.0


# ── T031: Testes multi-setor — industrial (PETROBRAS) + xfail banco ───────────


def test_industrial_all_15_indicators_inserted(db):
    """PETROBRAS: todas as contas dos perfis presentes → 20 indicadores."""
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_industrial_bpa.csv",
        FIXTURES_DIR / "sample_industrial_bpp.csv",
        FIXTURES_DIR / "sample_industrial_dre.csv",
    )
    count = db.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
    assert count == EXPECTED_INDICATOR_COUNT


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
    """PETROBRAS: nenhum indicador é None (todas as contas presentes)."""
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_industrial_bpa.csv",
        FIXTURES_DIR / "sample_industrial_bpp.csv",
        FIXTURES_DIR / "sample_industrial_dre.csv",
    )
    none_count = db.execute("SELECT COUNT(*) FROM indicators WHERE valor IS NULL").fetchone()[0]
    assert none_count == 0


def test_bank_sector_liquidez_seca_is_none(db):
    """BCO Brasil: liquidez_seca não é computável — sem estoques no perfil banking.

    ``estoques`` não existe no BPA de bancos: ausente do ACCOUNT_MAP banking
    por desenho (design 3.1/3.5) e listado na ``INDICATOR_POLICY`` do perfil.
    """
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_bank_bpa.csv",
        FIXTURES_DIR / "sample_bank_bpp.csv",
        FIXTURES_DIR / "sample_bank_dre.csv",
    )
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'liquidez_seca'").fetchone()
    assert row is not None
    assert row[0] is None


def test_bank_sector_divida_bruta_is_none(db):
    """BCO Brasil: divida_bruta não é computável — estrutura financeira COSIF.

    ``emprestimos_cp``/``emprestimos_lp`` (2.01.04/2.02.01) não existem no
    BPP de bancos (mensuração a valor justo/custo amortizado); sem dívida, a
    ``INDICATOR_POLICY`` banking exclui divida_bruta, divida_liquida e
    endividamentos.
    """
    _load_and_calc(
        db,
        FIXTURES_DIR / "sample_bank_bpa.csv",
        FIXTURES_DIR / "sample_bank_bpp.csv",
        FIXTURES_DIR / "sample_bank_dre.csv",
    )
    row = db.execute("SELECT valor FROM indicators WHERE indicador = 'divida_bruta'").fetchone()
    assert row is not None
    assert row[0] is None


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

    assert total == EXPECTED_INDICATOR_COUNT
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
            """
            SELECT indicador, valor FROM indicators
            WHERE cnpj_cia = ? AND dt_refer = ?
            """,
            [_TTM_CNPJ, '2024-09-30']
        ).fetchall()
    )

    # ROE = lucro_líquido / PL = 500 / 1000 * 100 = 50.0
    assert rows["roe"] == pytest.approx(50.0)
    # receita_liquida (3.01) entra via TTM = 369 + (494 - 377) = 486
    # margem_liquida = lucro_líquido (500) / receita_liquida (486) * 100
    assert rows["margem_liquida"] == pytest.approx(500 / 486 * 100)
