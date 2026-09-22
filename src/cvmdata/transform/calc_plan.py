"""Funções puras de cálculo de indicadores fundamentalistas e plano de cálculo."""

# ── Rentabilidade ─────────────────────────────────────────────────────────────


def giro_ativo(receita_liquida: float | None, ativo_total: float | None) -> float | None:
    """Receita Líquida / Ativo Total  |  3.01 / 1"""
    if receita_liquida is None or ativo_total is None:
        return None
    if ativo_total == 0:
        return None
    return receita_liquida / ativo_total


def margem_bruta(resultado_bruto: float | None, receita_liquida: float | None) -> float | None:
    """Resultado Bruto / Receita Líquida x 100  |  3.03 / 3.01"""
    if resultado_bruto is None or receita_liquida is None:
        return None
    if receita_liquida == 0:
        return None
    return resultado_bruto / receita_liquida * 100


def margem_ebit(ebit: float | None, receita_liquida: float | None) -> float | None:
    """EBIT / Receita Líquida x 100  |  3.05 / 3.01"""
    if ebit is None or receita_liquida is None:
        return None
    if receita_liquida == 0:
        return None
    return ebit / receita_liquida * 100


def margem_liquida(lucro_liquido: float | None, receita_liquida: float | None) -> float | None:
    """Lucro Líquido / Receita Líquida x 100  |  3.11 / 3.01"""
    if lucro_liquido is None or receita_liquida is None:
        return None
    if receita_liquida == 0:
        return None
    return lucro_liquido / receita_liquida * 100


def roe(lucro_liquido: float | None, patrimonio_liquido: float | None) -> float | None:
    """Lucro Líquido / Patrimônio Líquido x 100  |  3.11 / 2.03"""
    if lucro_liquido is None or patrimonio_liquido is None:
        return None
    if patrimonio_liquido == 0:
        return None
    return lucro_liquido / patrimonio_liquido * 100


def roa(lucro_liquido: float | None, ativo_total: float | None) -> float | None:
    """Lucro Líquido / Ativo Total x 100  |  3.11 / 1"""
    if lucro_liquido is None or ativo_total is None:
        return None
    if ativo_total == 0:
        return None
    return lucro_liquido / ativo_total * 100


# ── Liquidez ──────────────────────────────────────────────────────────────────


def capital_giro(
    ativo_circulante: float | None, passivo_circulante: float | None
) -> float | None:
    """AC - PC  |  1.01 - 2.01"""
    if ativo_circulante is None or passivo_circulante is None:
        return None
    
    return ativo_circulante - passivo_circulante


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
    """(AC - Estoques) / PC  |  (1.01 - 1.01.04) / 2.01"""
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
    """(PC + PNC) / AT x 100  |  (2.01 + 2.02) / 1"""
    if any(v is None for v in (passivo_circulante, passivo_nao_circulante, ativo_total)):
        return None
    if ativo_total == 0:
        return None
    return (passivo_circulante + passivo_nao_circulante) / ativo_total * 100  # type: ignore[operator]


def endividamento_pl(
    passivo_circulante: float | None,
    passivo_nao_circulante: float | None,
    patrimonio_liquido: float | None,
) -> float | None:
    """(PC + PNC) / PL x 100  | (2.01 + 2.02) / 2.03 x 100"""
    if any(v is None for v in (passivo_circulante, passivo_nao_circulante, patrimonio_liquido)):
        return None
    if patrimonio_liquido == 0:
        return None
    return (passivo_circulante + passivo_nao_circulante) / patrimonio_liquido * 100


def divida_bruta(emprestimos_cp: float | None, emprestimos_lp: float | None) -> float | None:
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
    """Dívida Bruta - Caixa - Aplicações  |  (2.01.04 + 2.02.01) - 1.01.01 - 1.01.02"""
    if any(
        v is None
        for v in (emprestimos_cp, emprestimos_lp, caixa_equivalentes, aplicacoes_financeiras)
    ):
        return None
    db = divida_bruta(emprestimos_cp, emprestimos_lp)
    return db - caixa_equivalentes - aplicacoes_financeiras  # type: ignore[operator]


def divida_liquida_pl(divida_liq: float | None, patrimonio_liquido: float | None) -> float | None:
    """Dívida Líquida / PL  |  derivado / 2.03"""
    if divida_liq is None or patrimonio_liquido is None:
        return None
    if patrimonio_liquido == 0:
        return None
    return divida_liq / patrimonio_liquido


def cobertura_juros(ebit: float | None, despesas_financeiras: float | None) -> float | None:
    """EBIT / Despesas Financeiras  |  3.05 / 3.06.02"""
    if ebit is None or despesas_financeiras is None:
        return None
    if despesas_financeiras == 0:
        return None
    return ebit / despesas_financeiras


# ── Tributos e NOPAT ────────────────────────────────────────────────────────


def taxa_efetiva_ir(
    imposto_renda_csll: float | None,
    resultado_antes_tributos: float | None,
) -> float | None:
    """Taxa efetiva de IR/CSLL, na convenção 'taxa positiva reduz o lucro'.

    imposto_renda_csll segue o sinal de resultado da CVM:
      negativo = despesa de imposto (~72% das linhas observadas em DFP 2025)
      positivo = benefício/crédito fiscal líquido (~24% das linhas)

    Por isso o sinal é invertido aqui: despesa (negativo) vira taxa positiva
    (reduz NOPAT abaixo do EBIT); benefício (positivo) vira taxa negativa
    (eleva NOPAT acima do EBIT) — ambos economicamente corretos e esperados.

    resultado_antes_tributos <= 0 (prejuízo) não tem taxa efetiva com leitura
    econômica válida — retorna None.
    """
    if imposto_renda_csll is None or resultado_antes_tributos is None:
        return None
    if resultado_antes_tributos <= 0:
        return None
    return -imposto_renda_csll / resultado_antes_tributos


def nopat(ebit: float | None, taxa_efetiva: float | None) -> float | None:
    """NOPAT = EBIT * (1 - taxa_efetiva).

    Pode superar o EBIT quando taxa_efetiva < 0 (empresa com benefício fiscal
    líquido no período) — comportamento esperado, não é erro de cálculo.
    """
    if ebit is None or taxa_efetiva is None:
        return None
    return ebit * (1 - taxa_efetiva)


def roic(
    nopat_val: float | None,
    patrimonio_liquido: float | None,
    emprestimos_cp: float | None,
    emprestimos_lp: float | None,
) -> float | None:
    """ROIC = NOPAT / Capital Investido x 100, onde
    Capital Investido = PL + Empréstimos CP + Empréstimos LP."""
    if any(
        v is None
        for v in (nopat_val, patrimonio_liquido, emprestimos_cp, emprestimos_lp)
    ):
        return None
    capital_investido = patrimonio_liquido + emprestimos_cp + emprestimos_lp
    if capital_investido == 0:
        return None
    return nopat_val / capital_investido * 100


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


def calc_nopat(comp: dict[str, float | None]) -> float | None:
    """Calcula NOPAT derivando a taxa efetiva de IR a partir do dict."""
    taxa = taxa_efetiva_ir(
        comp.get("imposto_renda_csll"),
        comp.get("resultado_antes_tributos"),
    )
    return nopat(comp.get("ebit"), taxa)


def calc_roic(comp: dict[str, float | None]) -> float | None:
    """Calcula ROIC derivando o NOPAT a partir do dict (padrão de divida_liquida_pl)."""
    np = calc_nopat(comp)
    return roic(
        np,
        comp.get("patrimonio_liquido"),
        comp.get("emprestimos_cp"),
        comp.get("emprestimos_lp"),
    )


# ── CALC PLAN ─────────────────────────────────────────────────────────────


# (nome do indicador, função, [nomes dos componentes])
CALC_PLAN: list[tuple[str, object, list[str]]] = [
    ("capital_giro", capital_giro, ["ativo_circulante", "passivo_circulante"]),
    ("cobertura_juros", cobertura_juros, ["ebit", "despesas_financeiras"]),
    ("divida_bruta", divida_bruta, ["emprestimos_cp", "emprestimos_lp"]),
    ("divida_liquida", divida_liquida, 
        ["emprestimos_cp", "emprestimos_lp", "caixa_equivalentes", "aplicacoes_financeiras"]),
    ("divida_liquida_pl", None, []),
    ("endividamento_geral", endividamento_geral, 
        ["passivo_circulante", "passivo_nao_circulante", "ativo_total"]),
    ("endividamento_pl", endividamento_pl, 
        ["passivo_circulante", "passivo_nao_circulante", "patrimonio_liquido"]),
    ("giro_ativo", giro_ativo, ["receita_liquida", "ativo_total"]),
    ("margem_bruta", margem_bruta, ["resultado_bruto", "receita_liquida"]),
    ("margem_ebit", margem_ebit, ["ebit", "receita_liquida"]),
    ("margem_liquida", margem_liquida, ["lucro_liquido", "receita_liquida"]),
    ("liquidez_corrente", liquidez_corrente, ["ativo_circulante", "passivo_circulante"]),
    ("liquidez_seca", liquidez_seca, ["ativo_circulante", "estoques", "passivo_circulante"]),
    ("liquidez_imediata", liquidez_imediata, ["caixa_equivalentes", "passivo_circulante"]),
    ("liquidez_geral", liquidez_geral, 
        ["ativo_circulante","realizavel_longo_prazo", "passivo_circulante", "passivo_nao_circulante"]),
    ("roa", roa, ["lucro_liquido", "ativo_total"]),
    ("roe", roe, ["lucro_liquido", "patrimonio_liquido"]),
    ("roic", None, []),
]


EXPECTED_INDICATOR_COUNT = len(CALC_PLAN)


# Indicadores inaplicáveis por perfil.
INDICATOR_POLICY: dict[str, set[str]] = {
    "banking": {
        "liquidez_seca",
        "liquidez_geral",
        "margem_ebit",
        "cobertura_juros",
        "divida_bruta",
        "divida_liquida",
        "divida_liquida_pl",
        "roic",
    },
}
