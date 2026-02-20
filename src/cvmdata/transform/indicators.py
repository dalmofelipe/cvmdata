"""Funções puras de cálculo de indicadores fundamentalistas + orquestrador.

Todas as funções puras:
  - Retornam float | None
  - Retornam None se qualquer argumento for None
  - Retornam None se o denominador for zero (sem ZeroDivisionError)
  - Nunca lançam exceção

Contas CVM de referência documentadas nos comentários inline.
"""
from __future__ import annotations

import logging

import duckdb

from cvmdata.ingestion.db import init_indicators_schema
from cvmdata.transform.account_map import ACCOUNT_MAP, get_component

logger = logging.getLogger(__name__)

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


def _calc_divida_liquida_pl(comp: dict[str, float | None]) -> float | None:
    """Calcula divida_liquida_pl derivando divida_liquida a partir do dict."""
    dl = divida_liquida(
        comp.get("emprestimos_cp"),
        comp.get("emprestimos_lp"),
        comp.get("caixa_equivalentes"),
        comp.get("aplicacoes_financeiras"),
    )
    return divida_liquida_pl(dl, comp.get("patrimonio_liquido"))


# (nome, função, [nomes dos componentes])
# divida_liquida_pl usa fn=None — tratado via _calc_divida_liquida_pl
_CALC_PLAN: list[tuple[str, object, list[str]]] = [
    ("roe",                roe,                ["lucro_liquido",      "patrimonio_liquido"]),
    ("roa",                roa,                ["lucro_liquido",      "ativo_total"]),
    ("margem_bruta",       margem_bruta,       ["resultado_bruto",    "receita_liquida"]),
    ("margem_operacional", margem_operacional, ["ebit",               "receita_liquida"]),
    ("margem_liquida",     margem_liquida,     ["lucro_liquido",      "receita_liquida"]),
    ("giro_ativo",         giro_ativo,         ["receita_liquida",    "ativo_total"]),
    ("liquidez_corrente",  liquidez_corrente,  ["ativo_circulante",   "passivo_circulante"]),
    ("liquidez_seca",      liquidez_seca,      ["ativo_circulante",   "estoques",             "passivo_circulante"]),  # noqa: E501
    ("liquidez_imediata",  liquidez_imediata,  ["caixa_equivalentes", "passivo_circulante"]),
    ("liquidez_geral",     liquidez_geral,     ["ativo_circulante",   "realizavel_longo_prazo","passivo_circulante","passivo_nao_circulante"]),  # noqa: E501
    ("endividamento_geral",endividamento_geral,["passivo_circulante", "passivo_nao_circulante","ativo_total"]),  # noqa: E501
    ("divida_bruta",       divida_bruta,       ["emprestimos_cp",     "emprestimos_lp"]),
    ("divida_liquida",     divida_liquida,     ["emprestimos_cp",     "emprestimos_lp",        "caixa_equivalentes","aplicacoes_financeiras"]),  # noqa: E501
    ("divida_liquida_pl",  None,               []),
    ("cobertura_juros",    cobertura_juros,    ["ebit",               "despesas_financeiras"]),
]


def _extract_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str,
    dt_refer: str,
) -> dict[str, float | None]:
    """Extrai todos os componentes mapeados para uma empresa/período."""
    placeholders = ", ".join(f"'{cd}'" for cd in ACCOUNT_MAP)
    rows = conn.execute(
        f"""
        SELECT CD_CONTA, VL_CONTA
        FROM (
            SELECT CD_CONTA, VL_CONTA FROM raw_bpa_clean
             WHERE CNPJ_CIA = ? AND DT_REFER = ?
            UNION ALL
            SELECT CD_CONTA, VL_CONTA FROM raw_bpp_clean
             WHERE CNPJ_CIA = ? AND DT_REFER = ?
            UNION ALL
            SELECT CD_CONTA, VL_CONTA FROM raw_dre_clean
             WHERE CNPJ_CIA = ? AND DT_REFER = ?
        )
        WHERE CD_CONTA IN ({placeholders})
        """,
        [cnpj, dt_refer, cnpj, dt_refer, cnpj, dt_refer],
    ).fetchall()

    comp: dict[str, float | None] = {}
    for cd_conta, vl_conta in rows:
        name = get_component(cd_conta)
        if name:
            comp[name] = float(vl_conta) if vl_conta is not None else None
    return comp


def _upsert_indicators(
    conn: duckdb.DuckDBPyConnection,
    cnpj_cia: str,
    dt_refer: str,
    comp: dict[str, float | None],
) -> int:
    """Insere/substitui os 15 indicadores para um par (cnpj_cia, dt_refer)."""
    rows: list[tuple[str, str, str, float | None]] = []
    for nome, fn, arg_names in _CALC_PLAN:
        if nome == "divida_liquida_pl":
            valor = _calc_divida_liquida_pl(comp)
        else:
            args = [comp.get(a) for a in arg_names]
            valor = fn(*args)  # type: ignore[operator]
        rows.append((cnpj_cia, dt_refer, nome, valor))
    conn.executemany(
        "INSERT OR REPLACE INTO indicators"  # noqa: E501
        " (cnpj_cia, dt_refer, indicador, valor) VALUES (?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def calculate_all(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> int:
    """Calcula os 15 indicadores para todas as empresas/períodos disponíveis.

    Args:
        conn: Conexão DuckDB com tabelas ``*_clean`` já criadas.
        cnpj: Se fornecido, processa apenas essa empresa.

    Returns:
        Número total de registros inseridos/substituídos em ``indicators``.
    """
    init_indicators_schema(conn)

    # Verifica se as tabelas clean existem antes de consultar
    existing = {
        r[0]
        for r in conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name IN ('raw_bpa_clean', 'raw_bpp_clean', 'raw_dre_clean')
            """
        ).fetchall()
    }
    if not existing:
        logger.warning("Tabelas *_clean ausentes — rode 'normalize' primeiro")
        return 0

    filter_sql = "WHERE CNPJ_CIA = ?" if cnpj else ""
    params = [cnpj] if cnpj else []
    clean_selects = " UNION ".join(
        f"SELECT CNPJ_CIA, DT_REFER FROM {t} {filter_sql}"
        for t in sorted(existing)
    )
    pairs = conn.execute(
        f"SELECT DISTINCT CNPJ_CIA, DT_REFER::VARCHAR FROM ({clean_selects}) "
        f"ORDER BY CNPJ_CIA, DT_REFER",
        params * len(existing) if params else [],
    ).fetchall()

    if not pairs:
        logger.warning("Nenhum dado nas tabelas *_clean — rode 'normalize' primeiro")
        return 0

    logger.info("Calculando indicadores para %d empresa/período(s)…", len(pairs))
    total = 0

    for cnpj_cia, dt_refer in pairs:
        try:
            comp = _extract_components(conn, cnpj_cia, dt_refer)
            total += _upsert_indicators(conn, cnpj_cia, dt_refer, comp)
        except Exception:
            logger.exception(
                "Erro ao calcular indicadores para %s %s — pulando", cnpj_cia, dt_refer
            )

    logger.info("Indicadores: %d registros gravados", total)
    return total
