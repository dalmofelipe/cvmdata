"""Testes unitários da resolução textual da cauda de resultado (dre_tail_map)."""

from __future__ import annotations

import pytest

from cvmdata.transform.dre_tail_map import (
    DRE_TAIL_TEXT_MAP,
    get_tail_component,
    normalize_ds_conta,
)

pytestmark = pytest.mark.unit


# --- normalize_ds_conta -----------------------------------------------------


def test_normalize_ds_conta_lowercases():
    assert normalize_ds_conta("Resultado Antes dos Tributos sobre o Lucro") == (
        "resultado antes dos tributos sobre o lucro"
    )


def test_normalize_ds_conta_strips_accents():
    assert normalize_ds_conta("Imposto de Renda e Contribuição Social sobre o Lucro") == (
        "imposto de renda e contribuicao social sobre o lucro"
    )


def test_normalize_ds_conta_trims_leading_trailing_spaces():
    assert normalize_ds_conta("  Lucro/Prejuízo Líquido Consolidado do Período  ") == (
        "lucro/prejuizo liquido consolidado do periodo"
    )


def test_normalize_ds_conta_mixed_case():
    assert normalize_ds_conta("RESULTADO Líquido Das Operações Continuadas") == (
        "resultado liquido das operacoes continuadas"
    )


# --- get_tail_component -----------------------------------------------------


@pytest.mark.parametrize(
    "ds_conta, expected",
    [
        ("Resultado Antes dos Tributos sobre o Lucro", "resultado_antes_tributos"),
        ("Imposto de Renda e Contribuição Social sobre o Lucro", "imposto_renda_csll"),
        ("Resultado Líquido das Operações Continuadas", "resultado_liquido_continuadas"),
        ("Lucro/Prejuízo Líquido das Operações Descontinuadas", "ajuste_descontinuadas"),
        ("Resultado Líquido das Operações Descontinuadas", "ajuste_descontinuadas"),
    ],
)
def test_get_tail_component_happy_path(ds_conta, expected):
    assert get_tail_component(ds_conta, "3.05") == expected


def test_get_tail_component_all_map_keys_resolvable():
    for text, component in DRE_TAIL_TEXT_MAP.items():
        assert get_tail_component(text, "3.05") == component


def test_get_tail_component_subconta_detalhe_returns_none():
    """Subconta de 3+ níveis fica fora de escopo por desenho, mesmo com texto batendo."""
    assert get_tail_component("Resultado Antes dos Tributos sobre o Lucro", "3.10.01.01") is None


def test_get_tail_component_unknown_text_returns_none():
    assert get_tail_component("Receita de Venda de Bens", "3.01") is None
    assert get_tail_component("EBIT", "3.05") is None


# ── Casos reais observados na investigação (apêndice do design) ─────────────


def test_dotz_subconta_detail_is_noise():
    """DOTZ '3.10.01.01' + texto de IR corrente → None (ruído de detalhamento)."""
    assert (
        get_tail_component(
            "Imposto de renda e contribuição social corrente", "3.10.01.01"
        )
        is None
    )


def test_btg_subconta_detail_is_noise():
    """BTG Pactual '3.01.01' + texto de instrumentos financeiros → None (ruído)."""
    assert (
        get_tail_component("Resultado líquido com instrumentos financeiros", "3.01.01")
        is None
    )