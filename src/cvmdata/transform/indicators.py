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
from collections import defaultdict

import duckdb

from cvmdata.ingestion.db import init_indicators_schema
from cvmdata.transform.account_map import ACCOUNT_MAP, get_component

logger = logging.getLogger(__name__)

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


def _get_ttm_value(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str,
    dt_refer: str,
    cd_conta: str,
) -> float | None:
    """Retorna o valor TTM (Trailing Twelve Months) para uma conta DRE.

    Fórmula: ``YTD_atual + (FY_anterior − YTD_anterior_mesmo_periodo)``

    Fallback chain (nunca levanta exceção):
    1. TTM completo          — ITR recente + PENÚLTIMO + DFP anterior disponíveis
    2. Sem PENÚLTIMO         — retorna ``FY_anterior`` direto
    3. Sem DFP anterior      — retorna ``YTD_atual`` (YTD parcial como proxy)
    4. Sem YTD atual (ITR)   — retorna ``FY_anterior`` se disponível, senão None

    Args:
        conn:     Conexão DuckDB com ``raw_dre_clean`` já populado.
        cnpj:     CNPJ da empresa (ex: ``"33.000.167/0001-01"``).
        dt_refer: Data de referência do período (ex: ``"2024-09-30"``).
        cd_conta: Código da conta CVM (ex: ``"3.01"``).

    Returns:
        Valor TTM como float, ou None se dados insuficientes.
    """
    # 1. YTD atual (ÚLTIMO, row já deduplicado pelo normalize_table com DT_INI ASC)
    ytd_row = conn.execute(
        """
        SELECT VL_CONTA FROM raw_dre_clean
        WHERE CNPJ_CIA = ? AND DT_REFER = ? AND CD_CONTA = ? AND ORDEM_EXERC = 'ÚLTIMO'
        """,
        [cnpj, dt_refer, cd_conta],
    ).fetchone()
    ytd_val: float | None = float(ytd_row[0]) if ytd_row and ytd_row[0] is not None else None

    # 2. YTD do ano anterior (PENÚLTIMO, mesmo DT_REFER)
    penu_row = conn.execute(
        """
        SELECT VL_CONTA FROM raw_dre_clean
        WHERE CNPJ_CIA = ? AND DT_REFER = ? AND CD_CONTA = ? AND ORDEM_EXERC = 'PENÚLTIMO'
        """,
        [cnpj, dt_refer, cd_conta],
    ).fetchone()
    penu_val: float | None = float(penu_row[0]) if penu_row and penu_row[0] is not None else None

    # 3. FY anterior: MAX(DT_FIM_EXERC) do DFP antes do DT_REFER
    fy_dt_row = conn.execute(
        """
        SELECT MAX(DT_FIM_EXERC) FROM raw_dre_clean
        WHERE CNPJ_CIA = ? AND source = 'dfp' AND DT_FIM_EXERC < ?
        """,
        [cnpj, dt_refer],
    ).fetchone()
    fy_val: float | None = None
    if fy_dt_row and fy_dt_row[0] is not None:
        fy_vl_row = conn.execute(
            """
            SELECT VL_CONTA FROM raw_dre_clean
            WHERE CNPJ_CIA = ? AND DT_FIM_EXERC = ? AND CD_CONTA = ? AND ORDEM_EXERC = 'ÚLTIMO'
            """,
            [cnpj, str(fy_dt_row[0]), cd_conta],
        ).fetchone()
        fy_val = float(fy_vl_row[0]) if fy_vl_row and fy_vl_row[0] is not None else None

    # Fallback chain
    if ytd_val is None:
        return fy_val                        # sem ITR recente
    if fy_val is None:
        return ytd_val                       # sem DFP anterior — YTD parcial
    if penu_val is None:
        return fy_val                        # sem PENÚLTIMO — FY completo como proxy
    return ytd_val + (fy_val - penu_val)     # TTM completo


def _fetch_all_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> dict[tuple[str, str], dict[str, float | None]]:
    """Batch query para BPA/BPP: retorna ``{(cnpj, dt_refer): {componente: valor}}``.

    Executa uma única query (UNION ALL de raw_bpa_clean + raw_bpp_clean) para
    todas as empresas/períodos, eliminando N round-trips para contas de balanço.
    """
    balance_codes = [cd for cd in ACCOUNT_MAP if not cd.startswith("3.")]
    placeholders = ", ".join(f"'{cd}'" for cd in balance_codes)
    filter_clause = "AND CNPJ_CIA = ?" if cnpj else ""
    params: list[str] = [cnpj] if cnpj else []

    rows = conn.execute(
        f"""
        SELECT CNPJ_CIA, DT_REFER::VARCHAR, CD_CONTA, VL_CONTA
        FROM (
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpa_clean
            UNION ALL
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpp_clean
        )
        WHERE CD_CONTA IN ({placeholders}) {filter_clause}
        ORDER BY CNPJ_CIA, DT_REFER
        """,
        params,
    ).fetchall()

    result: dict[tuple[str, str], dict[str, float | None]] = {}
    for cnpj_r, dt_r, cd_conta, vl_conta in rows:
        key = (cnpj_r, dt_r)
        if key not in result:
            result[key] = {}
        name = get_component(cd_conta)
        if name:
            result[key][name] = float(vl_conta) if vl_conta is not None else None
    return result


def _fetch_all_dre_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> dict[tuple[str, str], dict[str, float | None]]:
    """Batch fetch + cálculo TTM em memória para contas DRE.

    Executa uma única query (raw_dre_clean) com ``ORDEM_EXERC IN ('ÚLTIMO', 'PENÚLTIMO')``,
    agrupa os resultados em Python e aplica a fórmula TTM por ``(cnpj, dt_refer, cd_conta)``.

    Returns:
        ``{(cnpj, dt_refer): {componente_semantico: valor_ttm}}``
    """
    dre_codes = [cd for cd in ACCOUNT_MAP if cd.startswith("3.")]
    placeholders = ", ".join(f"'{cd}'" for cd in dre_codes)
    filter_clause = "AND CNPJ_CIA = ?" if cnpj else ""
    params: list[str] = [cnpj] if cnpj else []

    rows = conn.execute(
        f"""
        SELECT CNPJ_CIA, DT_REFER::VARCHAR, CD_CONTA, ORDEM_EXERC,
               VL_CONTA, source, DT_FIM_EXERC::VARCHAR
        FROM raw_dre_clean
        WHERE CD_CONTA IN ({placeholders})
          AND ORDEM_EXERC IN ('ÚLTIMO', 'PENÚLTIMO')
          {filter_clause}
        ORDER BY CNPJ_CIA, DT_REFER, CD_CONTA
        """,
        params,
    ).fetchall()

    # Índice: (cnpj, dt_refer, cd_conta, ordem_exerc) → (vl_conta, source, dt_fim_exerc)
    idx: dict[tuple[str, str, str, str], tuple[float | None, str, str]] = {}
    # Entradas DFP por empresa: cnpj → [(dt_fim_exerc, dt_refer)]
    dfp_entries: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for cnpj_r, dt_r, cd, ordem, vl, src, dt_fim in rows:
        vl_f: float | None = float(vl) if vl is not None else None
        idx[(cnpj_r, dt_r, cd, ordem)] = (vl_f, src or "", dt_fim or "")
        if src == "dfp" and ordem == "ÚLTIMO":
            dfp_entries[cnpj_r].append((dt_fim or "", dt_r))

    # Todos os pares (cnpj, dt_refer) que têm pelo menos uma linha ÚLTIMO
    all_pairs: set[tuple[str, str]] = {
        (cnpj_r, dt_r)
        for (cnpj_r, dt_r, _, ordem) in idx
        if ordem == "ÚLTIMO"
    }

    result: dict[tuple[str, str], dict[str, float | None]] = {}

    for cnpj_r, dt_r in all_pairs:
        # FY anterior: MAX(DT_FIM_EXERC) < DT_REFER de linhas DFP
        fy_dt_fim: str | None = max(
            (df for df, _ in dfp_entries.get(cnpj_r, []) if df < dt_r),
            default=None,
        )
        fy_dt_ref: str | None = None
        if fy_dt_fim:
            fy_dt_ref = next(
                (dr for df, dr in dfp_entries[cnpj_r] if df == fy_dt_fim),
                None,
            )

        comp: dict[str, float | None] = {}
        for cd in dre_codes:
            name = get_component(cd)
            if not name:
                continue

            ytd_row = idx.get((cnpj_r, dt_r, cd, "ÚLTIMO"))
            ytd_val: float | None = ytd_row[0] if ytd_row else None

            penu_row = idx.get((cnpj_r, dt_r, cd, "PENÚLTIMO"))
            penu_val: float | None = penu_row[0] if penu_row else None

            fy_val: float | None = None
            if fy_dt_ref:
                fy_row = idx.get((cnpj_r, fy_dt_ref, cd, "ÚLTIMO"))
                fy_val = fy_row[0] if fy_row else None

            # Fallback chain (mesma lógica de _get_ttm_value)
            if ytd_val is None:
                comp[name] = fy_val
            elif fy_val is None:
                comp[name] = ytd_val
            elif penu_val is None:
                comp[name] = fy_val
            else:
                comp[name] = ytd_val + (fy_val - penu_val)

        result[(cnpj_r, dt_r)] = comp

    return result


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

    Utiliza queries batch únicas (``_fetch_all_components`` + ``_fetch_all_dre_components``)
    em vez de N round-trips por par (cnpj, dt_refer). Contas de resultado (3.xx)
    usam TTM anualizado em vez de YTD parcial.

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

    # Batch fetch — duas queries para toda a base
    has_balance = bool(existing & {"raw_bpa_clean", "raw_bpp_clean"})
    balance_comps = _fetch_all_components(conn, cnpj) if has_balance else {}
    dre_comps = _fetch_all_dre_components(conn, cnpj) if "raw_dre_clean" in existing else {}

    all_pairs = set(balance_comps.keys()) | set(dre_comps.keys())

    if not all_pairs:
        logger.warning("Nenhum dado nas tabelas *_clean — rode 'normalize' primeiro")
        return 0

    logger.info("Calculando indicadores para %d empresa/período(s)…", len(all_pairs))
    total = 0

    for cnpj_cia, dt_refer in sorted(all_pairs):
        try:
            comp = {
                **balance_comps.get((cnpj_cia, dt_refer), {}),
                **dre_comps.get((cnpj_cia, dt_refer), {}),
            }
            total += _upsert_indicators(conn, cnpj_cia, dt_refer, comp)
        except Exception:
            logger.exception(
                "Erro ao calcular indicadores para %s %s — pulando", cnpj_cia, dt_refer
            )

    logger.info("Indicadores: %d registros gravados", total)
    return total
