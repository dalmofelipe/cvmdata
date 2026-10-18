"""Testes unitários da resolução por rótulo (text_map)."""

from __future__ import annotations

import pytest

from cvmdata.transform.text_map import (
    BPP_PL_TEXT_MAP,
    DRE_TAIL_TEXT_MAP,
    normalize_text,
    resolve_pl,
    resolve_tail,
)

pytestmark = pytest.mark.unit


# --- normalize_text -----------------------------------------------------


def test_normalize_text_lowercases():
    assert normalize_text("Resultado Antes dos Tributos sobre o Lucro") == (
        "resultado antes dos tributos sobre o lucro"
    )


def test_normalize_text_strips_accents():
    assert normalize_text("Imposto de Renda e Contribuição Social sobre o Lucro") == (
        "imposto de renda e contribuicao social sobre o lucro"
    )


def test_normalize_text_trims_leading_trailing_spaces():
    assert normalize_text("  Lucro/Prejuízo Líquido Consolidado do Período  ") == (
        "lucro/prejuizo liquido consolidado do periodo"
    )


def test_normalize_text_mixed_case():
    assert normalize_text("RESULTADO Líquido Das Operações Continuadas") == (
        "resultado liquido das operacoes continuadas"
    )


# --- resolve_tail -----------------------------------------------------


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
def test_resolve_tail_happy_path(ds_conta, expected):
    assert resolve_tail(ds_conta, "3.05") == expected


def test_resolve_tail_all_map_keys_resolvable():
    for text, component in DRE_TAIL_TEXT_MAP.items():
        assert resolve_tail(text, "3.05") == component


def test_resolve_tail_subconta_detalhe_returns_none():
    """Subconta de 3+ níveis fica fora de escopo por desenho, mesmo com texto batendo."""
    assert resolve_tail("Resultado Antes dos Tributos sobre o Lucro", "3.10.01.01") is None


def test_resolve_tail_unknown_text_returns_none():
    assert resolve_tail("Receita de Venda de Bens", "3.01") is None
    assert resolve_tail("EBIT", "3.05") is None


# ── Casos reais observados na investigação (apêndice do design) ─────────────


def test_dotz_subconta_detail_is_noise():
    """DOTZ '3.10.01.01' + texto de IR corrente → None (ruído de detalhamento)."""
    assert (
        resolve_tail(
            "Imposto de renda e contribuição social corrente", "3.10.01.01"
        )
        is None
    )


def test_btg_subconta_detail_is_noise():
    """BTG Pactual '3.01.01' + texto de instrumentos financeiros → None (ruído)."""
    assert (
        resolve_tail("Resultado líquido com instrumentos financeiros", "3.01.01")
        is None
    )

# --- resolve_pl (patrimônio líquido) ------------------------------------------


@pytest.mark.parametrize("cd_conta", ["2.03", "2.07", "2.08"])
def test_resolve_pl_by_label_regardless_of_code(cd_conta):
    """O PL aparece em três códigos no universo e o rótulo é o mesmo — é
    exatamente o caso que o código não resolve."""
    assert resolve_pl("Patrimônio Líquido Consolidado", cd_conta) == "patrimonio_liquido"


def test_resolve_pl_accepts_label_without_consolidado():
    """Prefixo em vez de igualdade: variação previsível não merece um mapa novo."""
    assert resolve_pl("Patrimônio Líquido", "2.03") == "patrimonio_liquido"
    assert resolve_pl("Patrimônio Líquido Total", "2.08") == "patrimonio_liquido"


@pytest.mark.parametrize(
    "ds_conta, cd_conta",
    [
        ("Provisões", "2.03"),
        ("Passivos Financeiros ao Custo Amortizado", "2.03"),
        ("Passivo Circulante", "2.01"),
    ],
)
def test_resolve_pl_returns_none_for_other_accounts(ds_conta, cd_conta):
    """2.03 no banking significa três coisas diferentes; só uma é PL."""
    assert resolve_pl(ds_conta, cd_conta) is None


def test_resolve_pl_rejects_codes_outside_bpp_pl_codes():
    assert resolve_pl("Patrimônio Líquido Consolidado", "2.01") is None
    assert resolve_pl("Patrimônio Líquido Consolidado", "2.07.01") is None


@pytest.mark.parametrize(
    "ds_conta",
    ["Patrimônio Líquido Ajustado", "Patrimônio Líquido Total", "PATRIMÔNIO LÍQUIDO"],
)
def test_resolve_pl_accepts_any_patrimonio_liquido_variant(ds_conta):
    """O prefixo cobre variação de cauda. Todo rótulo que começa com
    "Patrimônio Líquido" é patrimônio — o risco do prefixo seria capturar um
    conceito vizinho, e esse não existe no plano de contas."""
    assert resolve_pl(ds_conta, "2.03") == "patrimonio_liquido"


def test_resolve_pl_map_keys_are_normalized():
    for prefix in BPP_PL_TEXT_MAP:
        assert normalize_text(prefix) == prefix
