"""Funções puras de cálculo de indicadores fundamentalistas e plano de cálculo."""
from __future__ import annotations

from cvmdata.transform.account_map import ACCOUNT_MAP

# Contas de resultado (3.xx) — usam TTM em vez de YTD parcial
DRE_ACCOUNTS: frozenset[str] = frozenset(
    v for k, v in ACCOUNT_MAP.items() if k.startswith("3.")
)

# ── Rentabilidade ─────────────────────────────────────────────────────────────

def roe(lucro_liquido: float | None, patrimonio_liquido: float | None) -> float | None:
    """Lucro Líquido / Patrimônio Líquido × 100  |  3.11 / 2.03"""
    if lucro_liquido is None or patrimonio_liquido is None:
        return None
    if patrimonio_liquido == 0:
        return None
    return lucro_liquido / patrimonio_liquido * 100

def roa(lucro_liquido: float | None, ativo_total: float | None) -> float | None:
    """Lucro Líquido / Ativo Total × 100  |  3.11 / 1"""
    if lucro_liquido is None or ativo_total is None:
        return None
    if ativo_total == 0:
        return None
    return lucro_liquido / ativo_total * 100

def margem_bruta(resultado_bruto: float | None, receita_liquida: float | None) -> float | None:
    """Resultado Bruto / Receita Líquida × 100  |  3.03 / 3.01"""
    if resultado_bruto is None or receita_liquida is None:
        return None
    if receita_liquida == 0:
        return None
    return resultado_bruto / receita_liquida * 100

def margem_operacional(ebit: float | None, receita_liquida: float | None) -> float | None:
    """EBIT / Receita Líquida × 100  |  3.05 / 3.01"""
    if ebit is None or receita_liquida is None:
        return None
    if receita_liquida == 0:
        return None
    return ebit / receita_liquida * 100

def margem_liquida(lucro_liquido: float | None, receita_liquida: float | None) -> float | None:
    """Lucro Líquido / Receita Líquida × 100  |  3.11 / 3.01"""
    if lucro_liquido is None or receita_liquida is None:
        return None
    if receita_liquida == 0:
        return None
    return lucro_liquido / receita_liquida * 100

def giro_ativo(receita_liquida: float | None, ativo_total: float | None) -> float | None:
    """Receita Líquida / Ativo Total  |  3.01 / 1"""
    if receita_liquida is None or ativo_total is None:
        return None
    if ativo_total == 0:
        return None
    return receita_liquida / ativo_total

# ── Liquidez ──────────────────────────────────────────────────────────────────

def liquidez_corrente(
    ativo_circulante: float | None, passivo_circulante: float | None
) -> float | None:
    """AC / PC  |  1.01 / 2.01"""
    if ativo_circulante is None or passivo_circulante is None:
        return None
    if passivo_circulante == 0:
        return None
    return ativo_circulante / passivo_circulante

def liquidez_seca(
    ativo_circulante: float | None,
    estoques: float | None,
    passivo_circulante: float | None,
) -> float | None:
    """(AC − Estoques) / PC  |  (1.01 − 1.01.04) / 2.01"""
    if ativo_circulante is None or estoques is None or passivo_circulante is None:
        return None
    if passivo_circulante == 0:
        return None
    return (ativo_circulante - estoques) / passivo_circulante

def liquidez_imediata(
    caixa_equivalentes: float | None, passivo_circulante: float | None
) -> float | None:
    """Caixa / PC  |  1.01.01 / 2.01"""
    if caixa_equivalentes is None or passivo_circulante is None:
        return None
    if passivo_circulante == 0:
        return None
    return caixa_equivalentes / passivo_circulante

def liquidez_geral(
    ativo_circulante: float | None,
    realizavel_lp: float | None,
    passivo_circulante: float | None,
    passivo_nao_circulante: float | None,
) -> float | None:
    """(AC + RLP) / (PC + PNC)  |  (1.01 + 1.02.01) / (2.01 + 2.02)"""
    if any(
        v is None
        for v in (ativo_circulante, realizavel_lp, passivo_circulante, passivo_nao_circulante)
    ):
        return None
    denom = passivo_circulante + passivo_nao_circulante  # type: ignore[operator]
    if denom == 0:
        return None
    return (ativo_circulante + realizavel_lp) / denom  # type: ignore[operator]

# ── Endividamento ─────────────────────────────────────────────────────────────

def endividamento_geral(
    passivo_circulante: float | None,
    passivo_nao_circulante: float | None,
    ativo_total: float | None,
) -> float | None:
    """(PC + PNC) / AT × 100  |  (2.01 + 2.02) / 1"""
    if any(v is None for v in (passivo_circulante, passivo_nao_circulante, ativo_total)):
        return None
    if ativo_total == 0:
        return None
    return (passivo_circulante + passivo_nao_circulante) / ativo_total * 100  # type: ignore[operator]

def divida_bruta(
    emprestimos_cp: float | None, emprestimos_lp: float | None
) -> float | None:
    """Emprést. CP + LP  |  2.01.04 + 2.02.01"""
    if emprestimos_cp is None or emprestimos_lp is None:
        return None
    return emprestimos_cp + emprestimos_lp

def divida_liquida(
    emprestimos_cp: float | None,
    emprestimos_lp: float | None,
    caixa_equivalentes: float | None,
    aplicacoes_financeiras: float | None,
) -> float | None:
    """Dívida Bruta − Caixa − Aplicações  |  (2.01.04+2.02.01) − 1.01.01 − 1.01.02"""
    if any(
        v is None
        for v in (emprestimos_cp, emprestimos_lp, caixa_equivalentes, aplicacoes_financeiras)
    ):
        return None
    db = divida_bruta(emprestimos_cp, emprestimos_lp)
    return db - caixa_equivalentes - aplicacoes_financeiras  # type: ignore[operator]

def divida_liquida_pl(
    divida_liq: float | None, patrimonio_liquido: float | None
) -> float | None:
    """Dívida Líquida / PL  |  derivado / 2.03"""
    if divida_liq is None or patrimonio_liquido is None:
        return None
    if patrimonio_liquido == 0:
        return None
    return divida_liq / patrimonio_liquido

def cobertura_juros(
    ebit: float | None, despesas_financeiras: float | None
) -> float | None:
    """EBIT / Despesas Financeiras  |  3.05 / 3.06.02"""
    if ebit is None or despesas_financeiras is None:
        return None
    if despesas_financeiras == 0:
        return None
    return ebit / despesas_financeiras

# ── Orquestrador ─────────────────────────────────────────────────────────────

def calc_divida_liquida_pl(comp: dict[str, float | None]) -> float | None:
    """Calcula divida_liquida_pl derivando divida_liquida a partir do dict."""
    dl = divida_liquida(
        comp.get("emprestimos_cp"),
        comp.get("emprestimos_lp"),
        comp.get("caixa_equivalentes"),
        comp.get("aplicacoes_financeiras"),
    )
    return divida_liquida_pl(dl, comp.get("patrimonio_liquido"))

# (nome, função, [nomes dos componentes])
# divida_liquida_pl usa fn=None — tratado via calc_divida_liquida_pl
CALC_PLAN: list[tuple[str, object, list[str]]] = [
    ("roe",                roe,                ["lucro_liquido",      "patrimonio_liquido"]),
    ("roa",                roa,                ["lucro_liquido",      "ativo_total"]),
    ("margem_bruta",       margem_bruta,       ["resultado_bruto",    "receita_liquida"]),
    ("margem_operacional", margem_operacional, ["ebit",               "receita_liquida"]),
    ("margem_liquida",     margem_liquida,     ["lucro_liquido",      "receita_liquida"]),
    ("giro_ativo",         giro_ativo,         ["receita_liquida",    "ativo_total"]),
    ("liquidez_corrente",  liquidez_corrente,  ["ativo_circulante",   "passivo_circulante"]),
    ("liquidez_seca",      liquidez_seca,      ["ativo_circulante",   "estoques",               "passivo_circulante"]),
    ("liquidez_imediata",  liquidez_imediata,  ["caixa_equivalentes", "passivo_circulante"]),
    ("liquidez_geral",     liquidez_geral,     ["ativo_circulante",   "realizavel_longo_prazo", "passivo_circulante", "passivo_nao_circulante"]),
    ("endividamento_geral",endividamento_geral,["passivo_circulante", "passivo_nao_circulante", "ativo_total"]),
    ("divida_bruta",       divida_bruta,       ["emprestimos_cp",     "emprestimos_lp"]),
    ("divida_liquida",     divida_liquida,     ["emprestimos_cp",     "emprestimos_lp",         "caixa_equivalentes", "aplicacoes_financeiras"]),
    ("divida_liquida_pl",  None,               []),
    ("cobertura_juros",    cobertura_juros,    ["ebit",               "despesas_financeiras"]),
]
