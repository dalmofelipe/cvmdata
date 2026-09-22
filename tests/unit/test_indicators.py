"""Testes unitários das funções puras de indicadores e mapeamento de contas."""

from __future__ import annotations

import inspect

import pytest

from cvmdata.transform.account_map import ACCOUNT_MAP, get_component
from cvmdata.transform.calc_plan import (
    CALC_PLAN,
    capital_giro,
    cobertura_juros,
    divida_bruta,
    divida_liquida,
    divida_liquida_pl,
    endividamento_geral,
    endividamento_pl,
    giro_ativo,
    liquidez_corrente,
    liquidez_geral,
    liquidez_imediata,
    liquidez_seca,
    margem_bruta,
    margem_ebit,
    margem_liquida,
    nopat,
    roa,
    roe,
    roic,
    taxa_efetiva_ir,
)
from cvmdata.transform.dre_tail_map import DRE_TAIL_TEXT_MAP

pytestmark = pytest.mark.unit


# --- ACCOUNT_MAP --------------------------------------------------------


_DEFAULT_EXPECTED_CODES = {
    # BPA
    "1",
    "1.01",
    "1.01.01",
    "1.01.02",
    "1.01.04",
    "1.02",
    "1.02.01",
    # BPP
    "2",
    "2.01",
    "2.01.04",
    "2.02",
    "2.02.01",
    "2.03",
    # DRE
    "3.01",
    "3.03",
    "3.05",
    "3.06.02",
    "3.11",
}


def test_account_map_has_expected_keys():
    assert set(ACCOUNT_MAP.keys()) == {"default", "banking"}
    assert set(ACCOUNT_MAP["default"].keys()) == _DEFAULT_EXPECTED_CODES


def test_account_map_banking_keys():
    """Banking: estrutura própria, sem contas que não existem no perfil."""
    assert set(ACCOUNT_MAP["banking"].keys()) == {
        "1",
        "1.01",
        "1.02",
        "2",
        "2.01",
        "2.02",
        "2.07",
        "3.01",
        "3.02",
        "3.03",
        "3.11",
    }
    assert ACCOUNT_MAP["banking"]["1.01"] == "caixa_equivalentes"
    assert ACCOUNT_MAP["banking"]["2.07"] == "patrimonio_liquido"
    assert ACCOUNT_MAP["banking"]["3.02"] == "despesas_financeiras"
    # Contas sem equivalente honesto em banking ficam de fora (design 3.1/3.5)
    for code in ("1.01.01", "1.01.04", "1.02.01", "2.01.04", "2.02.01", "2.03", "3.05"):
        assert code not in ACCOUNT_MAP["banking"]


def test_account_map_values_are_unique_per_profile():
    """Unicidade por perfil — nomes podem se repetir entre perfis (por desenho)."""
    for profile_id, profile_map in ACCOUNT_MAP.items():
        components = list(profile_map.values())
        assert len(components) == len(set(components)), profile_id


def test_account_map_known_mappings():
    """Spot-check - Uma troca aqui vira erro financeiro silencioso 
    em divida_bruta/divida_liquida/cobertura_juros."""
    assert get_component("2.01.04") == "emprestimos_cp"
    assert get_component("2.02.01") == "emprestimos_lp"


# --- CALC_PLAN --------------------------------------------------------


_SPECIAL_CASE_INDICATORS = {"divida_liquida_pl", "roic"}


def test_calc_plan_indicator_names_are_unique():
    names = [name for name, _, _ in CALC_PLAN]
    assert len(names) == len(set(names))


def test_calc_plan_arg_names_match_account_map_components():
    valid_components = {
        c for profile in ACCOUNT_MAP.values() for c in profile.values()
    } | set(DRE_TAIL_TEXT_MAP.values())

    for name, _fn, arg_names in CALC_PLAN:
        if name in _SPECIAL_CASE_INDICATORS:
            continue
        unknown = set(arg_names) - valid_components
        assert not unknown, f"{name}: arg_names desconhecidos {unknown}"


def test_calc_plan_arg_count_matches_function_signature():
    for name, fn, arg_names in CALC_PLAN:
        if name in _SPECIAL_CASE_INDICATORS:
            assert fn is None
            assert arg_names == []
            continue
        params = inspect.signature(fn).parameters
        assert len(arg_names) == len(params), (
            f"{name}: {len(arg_names)} arg_names vs "
            f"{len(params)} parâmetros de {fn.__name__}"
        )


def test_calc_plan_has_expected_indicator_names():
    expected = {
        "capital_giro",
        "cobertura_juros",
        "divida_bruta",
        "divida_liquida_pl",
        "divida_liquida",
        "endividamento_geral",
        "endividamento_pl",
        "giro_ativo",
        "liquidez_corrente",
        "liquidez_geral",
        "liquidez_imediata",
        "liquidez_seca",
        "margem_bruta",
        "margem_ebit",
        "margem_liquida",
        "roa",
        "roe",
        "roic",
    }
    names = {name for name, _, _ in CALC_PLAN}
    assert names == expected


# --- Cálculo dos indicadores e mapeamento de contas. ---


def test_get_component_known():
    assert get_component("1") == "ativo_total"
    assert get_component("3.11") == "lucro_liquido"
    assert get_component("2.03") == "patrimonio_liquido"


def test_get_component_unknown_returns_none():
    assert get_component("9.99.99") is None


def test_get_component_with_profile():
    assert get_component("2.07", "banking") == "patrimonio_liquido"
    assert get_component("3.02", "banking") == "despesas_financeiras"
    assert get_component("1.01", "banking") == "caixa_equivalentes"
    assert get_component("2.03", "banking") is None
    assert get_component("2.07") is None  # default não conhece a cauda


def test_get_component_unknown_profile_falls_back_to_default():
    """Perfil desconhecido cai no mapa 'default' sem lançar exceção."""
    assert get_component("2.03", "insurance") == "patrimonio_liquido"
    assert get_component("2.07", "insurance") is None


def test_roe_happy():
    assert roe(100, 500) == pytest.approx(20.0)


def test_roa_happy():
    assert roa(100, 2000) == pytest.approx(5.0)


def test_margem_bruta_happy():
    assert margem_bruta(300, 1000) == pytest.approx(30.0)


def test_margem_ebit_happy():
    assert margem_ebit(200, 1000) == pytest.approx(20.0)


def test_margem_liquida_happy():
    assert margem_liquida(150, 1000) == pytest.approx(15.0)


def test_giro_ativo_happy():
    assert giro_ativo(1000, 2000) == pytest.approx(0.5)


def test_liquidez_corrente_happy():
    assert liquidez_corrente(200, 100) == pytest.approx(2.0)


def test_liquidez_seca_happy():
    assert liquidez_seca(200, 50, 100) == pytest.approx(1.5)


def test_liquidez_imediata_happy():
    assert liquidez_imediata(80, 100) == pytest.approx(0.8)


def test_liquidez_geral_happy():
    assert liquidez_geral(200, 50, 100, 150) == pytest.approx(1.0)


def test_endividamento_geral_happy():
    assert endividamento_geral(100, 200, 1000) == pytest.approx(30.0)


def test_divida_bruta_happy():
    assert divida_bruta(300, 400) == pytest.approx(700.0)


def test_divida_liquida_happy():
    assert divida_liquida(300, 400, 80, 120) == pytest.approx(500.0)


def test_divida_liquida_pl_happy():
    assert divida_liquida_pl(500, 1000) == pytest.approx(0.5)


def test_cobertura_juros_happy():
    assert cobertura_juros(200, 50) == pytest.approx(4.0)


def test_capital_giro_happy():
    assert capital_giro(200, 100) == pytest.approx(100.0)


@pytest.mark.parametrize(
    "fn,args",
    [
        (cobertura_juros, (200, 0)),
        (divida_liquida_pl, (500, 0)),
        (endividamento_geral, (100, 200, 0)),
        (endividamento_pl, (100, 200, 0)),
        (giro_ativo, (1000, 0)),
        (liquidez_corrente, (200, 0)),
        (liquidez_geral, (200, 50, 0, 0)),
        (liquidez_imediata, (80, 0)),
        (liquidez_seca, (200, 50, 0)),
        (margem_bruta, (300, 0)),
        (margem_ebit, (200, 0)),
        (margem_liquida, (150, 0)),
        (roa, (100, 0)),
        (roe, (100, 0)),
    ],
)
def test_zero_denominator_returns_none(fn, args):
    assert fn(*args) is None


@pytest.mark.parametrize(
    "fn,args",
    [
        (capital_giro, (None, 100)),
        (cobertura_juros, (None, 50)),
        (divida_bruta, (None, 400)),
        (divida_liquida_pl, (None, 1000)),
        (divida_liquida, (None, 400, 80, 120)),
        (endividamento_geral, (None, 200, 1000)),
        (endividamento_pl, (None, 200, 1000)),
        (giro_ativo, (None, 2000)),
        (liquidez_corrente, (None, 100)),
        (liquidez_geral, (None, 50, 100, 150)),
        (liquidez_imediata, (None, 100)),
        (liquidez_seca, (200, None, 100)),
        (liquidez_seca, (None, 50, 100)),
        (margem_bruta, (None, 1000)),
        (margem_ebit, (None, 1000)),
        (margem_liquida, (None, 1000)),
        (roa, (None, 2000)),
        (roe, (100, None)),
        (roe, (None, 500)),
    ],
)
def test_none_argument_returns_none(fn, args):
    assert fn(*args) is None


# ── NOPAT / taxa efetiva de IR (design seção 3.6) ───────────────────────────


def test_taxa_efetiva_ir_despesa_normal():
    # imposto negativo (despesa) → taxa positiva
    assert taxa_efetiva_ir(-100, 300) == pytest.approx(0.3333, abs=1e-4)


def test_taxa_efetiva_ir_beneficio_fiscal():
    # imposto positivo (crédito/benefício) → taxa negativa
    assert taxa_efetiva_ir(100, 300) == pytest.approx(-0.3333, abs=1e-4)


def test_taxa_efetiva_ir_prejuizo_retorna_none():
    assert taxa_efetiva_ir(-50, -200) is None
    assert taxa_efetiva_ir(-50, 0) is None


def test_taxa_efetiva_ir_none_inputs():
    assert taxa_efetiva_ir(None, 300) is None
    assert taxa_efetiva_ir(-100, None) is None


def test_nopat_com_beneficio_fiscal_supera_ebit():
    taxa = taxa_efetiva_ir(100, 300)  # -0.3333
    assert nopat(1000, taxa) > 1000


def test_nopat_com_despesa_normal_fica_abaixo_ebit():
    taxa = taxa_efetiva_ir(-100, 300)  # +0.3333
    assert nopat(1000, taxa) < 1000


def test_nopat_none_inputs():
    assert nopat(None, 0.3) is None
    assert nopat(1000, None) is None


def test_roic_happy():
    # NOPAT=200, PL=1000, CP=200, LP=300 → 200/(1000+200+300)*100 = 13.33
    assert roic(200, 1000, 200, 300) == pytest.approx(13.3333, abs=1e-4)


def test_roic_any_none_returns_none():
    assert roic(None, 1000, 200, 300) is None
    assert roic(200, None, 200, 300) is None
    assert roic(200, 1000, None, 300) is None
    assert roic(200, 1000, 200, None) is None


def test_roic_zero_capital_investido_returns_none():
    assert roic(200, 0, 0, 0) is None
