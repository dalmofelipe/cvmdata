"""Fetch batch de contas de balanço (BPA/BPP) — sem TTM, valor pontual do período."""

from __future__ import annotations

import duckdb

from cvmdata.transform.account_map import ACCOUNT_MAP, get_component
from cvmdata.transform.indicators.ttm import Components


def _fetch_all_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> Components:
    """Batch query para BPA/BPP: retorna ``{(cnpj, dt_refer): {componente: valor}}``.

    Executa uma única query (UNION ALL de raw_bpa_clean + raw_bpp_clean) para
    todas as empresas/períodos.
    
    Contas de balanço não usam TTM — o valor é o saldo pontual do período.
    """
    balance_codes = [cd for cd in ACCOUNT_MAP if not cd.startswith("3.")]
    filter_clause = "AND CNPJ_CIA = ?" if cnpj else ""

    params: list[object] = [balance_codes]
    if cnpj:
        params.append(cnpj)

    params.append(balance_codes)
    if cnpj:
        params.append(cnpj)

    rows = conn.execute(
        f"""
        SELECT CNPJ_CIA, DT_REFER::VARCHAR, CD_CONTA, VL_CONTA
        FROM (
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpa_clean
            WHERE CD_CONTA = ANY(?) {filter_clause}
            UNION ALL
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpp_clean
            WHERE CD_CONTA = ANY(?) {filter_clause}
        )
        """,
        params,
    ).fetchall()

    result: Components = {}
    for cnpj_r, dt_r, cd_conta, vl_conta in rows:
        name = get_component(cd_conta)
        if name:
            valor = float(vl_conta) if vl_conta is not None else None
            result.setdefault((cnpj_r, dt_r), {})[name] = valor

    return result