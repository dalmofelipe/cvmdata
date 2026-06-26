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
from cvmdata.transform.calc_plan import CALC_PLAN, calc_divida_liquida_pl

logger = logging.getLogger(__name__)


def _get_ttm_value(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str,
    dt_refer: str,
    cd_conta: str,
) -> float | None:
    """Retorna o valor TTM (Trailing Twelve Months) para uma conta DRE.

    WARNING: This function executes 3–4 SQL queries per call. It is a
    utility for isolated unit testing ONLY. Never call this function
    inside a loop over company/period pairs — use _fetch_all_dre_components
    for batch processing. Wiring this into calculate_all would regress
    performance to ~280,000 SQL round-trips.

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
        return fy_val  # sem ITR recente
    if fy_val is None:
        return ytd_val  # sem DFP anterior — YTD parcial
    if penu_val is None:
        return fy_val  # sem PENÚLTIMO — FY completo como proxy
    return ytd_val + (fy_val - penu_val)  # TTM completo


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

    # When cnpj filter is present, params must be duplicated for each UNION branch
    if cnpj:
        params: list[str] = [cnpj, cnpj]
    else:
        params = []

    rows = conn.execute(
        f"""
        SELECT CNPJ_CIA, DT_REFER::VARCHAR, CD_CONTA, VL_CONTA
        FROM (
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpa_clean
            WHERE CD_CONTA IN ({placeholders}) {filter_clause}
            UNION ALL
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpp_clean
            WHERE CD_CONTA IN ({placeholders}) {filter_clause}
        )
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
    dre_codes = [code for code in ACCOUNT_MAP if code.startswith("3.")]
    placeholders = ", ".join(f"'{code}'" for code in dre_codes)
    filter_clause = "AND CNPJ_CIA = ?" if cnpj else ""
    params: list[str] = [cnpj] if cnpj else []

    rows = conn.execute(
        f"""
        SELECT
            CNPJ_CIA,
            DT_REFER::VARCHAR,
            CD_CONTA,
            ORDEM_EXERC,
            VL_CONTA,
            source,
            DT_FIM_EXERC::VARCHAR
        FROM raw_dre_clean
        WHERE CD_CONTA IN ({placeholders})
            AND ORDEM_EXERC IN ('ÚLTIMO', 'PENÚLTIMO') {filter_clause}
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
        (cnpj_r, dt_r) for (cnpj_r, dt_r, _, ordem) in idx if ordem == "ÚLTIMO"
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


def _build_indicator_rows(
    cnpj_cia: str,
    dt_refer: str,
    comp: dict[str, float | None],
) -> list[tuple[str, str, str, float | None]]:
    """Calcula os 15 indicadores para um par (cnpj_cia, dt_refer) e retorna as linhas.

    Não acessa o banco — apenas computa valores a partir do dict de componentes.
    """
    rows: list[tuple[str, str, str, float | None]] = []
    for nome, fn, arg_names in CALC_PLAN:
        if nome == "divida_liquida_pl":
            valor = calc_divida_liquida_pl(comp)
        else:
            args = [comp.get(a) for a in arg_names]
            valor = fn(*args)  # type: ignore[operator]
        rows.append((cnpj_cia, dt_refer, nome, valor))
    return rows


def calculate_all(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> int:
    """Calcula os 15 indicadores para todas as empresas/períodos disponíveis.

    Utiliza queries batch únicas (``_fetch_all_components`` + ``_fetch_all_dre_components``)
    em vez de N round-trips por par (cnpj, dt_refer). Contas de resultado (3.xx)
    usam TTM anualizado em vez de YTD parcial. O cálculo dos valores é feito em
    memória e persistido em um único ``executemany`` dentro de uma transação
    explícita — eliminando N commits individuais por par (cnpj, dt_refer).

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

    # Acumula todas as linhas em memória — INSERT único ao final
    all_rows: list[tuple[str, str, str, float | None]] = []
    for cnpj_cia, dt_refer in sorted(all_pairs):
        try:
            comp = {
                **balance_comps.get((cnpj_cia, dt_refer), {}),
                **dre_comps.get((cnpj_cia, dt_refer), {}),
            }
            all_rows.extend(_build_indicator_rows(cnpj_cia, dt_refer, comp))
        except Exception:
            logger.exception(
                "Erro ao calcular indicadores para %s %s — pulando", cnpj_cia, dt_refer
            )

    # Bulk insert: TRUNCATE + INSERT em transação única (evita N commits)
    conn.execute("BEGIN")
    try:
        cnpj_filter = f"WHERE cnpj_cia = '{cnpj}'" if cnpj else ""
        conn.execute(f"DELETE FROM indicators {cnpj_filter}")
        conn.executemany(
            "INSERT INTO indicators (cnpj_cia, dt_refer, indicador, valor) VALUES (?, ?, ?, ?)",
            all_rows,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    total = len(all_rows)
    logger.info("Indicadores: %d registros gravados", total)
    return total
