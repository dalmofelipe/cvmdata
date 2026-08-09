"""Testes unitários das funções puras de indicadores e mapeamento de contas."""

from __future__ import annotations

import inspect

import pytest

from cvmdata.transform.account_map import ACCOUNT_MAP, get_component
from cvmdata.transform.calc_plan import (
    CALC_PLAN,
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

pytestmark = pytest.mark.unit


# --- ACCOUNT_MAP --------------------------------------------------------


def test_account_map_has_expected_keys():
    expected_codes = {
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
    assert set(ACCOUNT_MAP.keys()) == expected_codes


def test_account_map_values_are_unique():
    components = list(ACCOUNT_MAP.values())
    assert len(components) == len(set(components))


def test_account_map_known_mappings():
    """Spot-check - Uma troca aqui vira erro financeiro silencioso 
    em divida_bruta/divida_liquida/cobertura_juros."""
    assert get_component("2.01.04") == "emprestimos_cp"
    assert get_component("2.02.01") == "emprestimos_lp"


# --- CALC_PLAN --------------------------------------------------------


_SPECIAL_CASE_INDICATOR = "divida_liquida_pl"


def test_calc_plan_indicator_names_are_unique():
    names = [name for name, _, _ in CALC_PLAN]
    assert len(names) == len(set(names))


def test_calc_plan_arg_names_match_account_map_components():
    valid_components = set(ACCOUNT_MAP.values())

    for name, _fn, arg_names in CALC_PLAN:
        if name == _SPECIAL_CASE_INDICATOR:
            continue
        unknown = set(arg_names) - valid_components
        assert not unknown, f"{name}: arg_names desconhecidos {unknown}"


def test_calc_plan_arg_count_matches_function_signature():
    for name, fn, arg_names in CALC_PLAN:
        if name == _SPECIAL_CASE_INDICATOR:
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
        "roe",
        "roa",
        "margem_bruta",
        "margem_operacional",
        "margem_liquida",
        "giro_ativo",
        "liquidez_corrente",
        "liquidez_seca",
        "liquidez_imediata",
        "liquidez_geral",
        "endividamento_geral",
        "divida_bruta",
        "divida_liquida",
        "divida_liquida_pl",
        "cobertura_juros",
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


@pytest.mark.parametrize(
    "fn,args",
    [
        (roe, (100, 0)),
        (roa, (100, 0)),
        (margem_bruta, (300, 0)),
        (margem_operacional, (200, 0)),
        (margem_liquida, (150, 0)),
        (giro_ativo, (1000, 0)),
        (liquidez_corrente, (200, 0)),
        (liquidez_seca, (200, 50, 0)),
        (liquidez_imediata, (80, 0)),
        (liquidez_geral, (200, 50, 0, 0)),
        (endividamento_geral, (100, 200, 0)),
        (divida_liquida_pl, (500, 0)),
        (cobertura_juros, (200, 0)),
    ],
)
def test_zero_denominator_returns_none(fn, args):
    assert fn(*args) is None


@pytest.mark.parametrize(
    "fn,args",
    [
        (roe, (None, 500)),
        (roe, (100, None)),
        (roa, (None, 2000)),
        (margem_bruta, (None, 1000)),
        (margem_operacional, (None, 1000)),
        (margem_liquida, (None, 1000)),
        (giro_ativo, (None, 2000)),
        (liquidez_corrente, (None, 100)),
        (liquidez_seca, (None, 50, 100)),
        (liquidez_seca, (200, None, 100)),
        (liquidez_imediata, (None, 100)),
        (liquidez_geral, (None, 50, 100, 150)),
        (endividamento_geral, (None, 200, 1000)),
        (divida_bruta, (None, 400)),
        (divida_liquida, (None, 400, 80, 120)),
        (divida_liquida_pl, (None, 1000)),
        (cobertura_juros, (None, 50)),
    ],
)
def test_none_argument_returns_none(fn, args):
    assert fn(*args) is None
