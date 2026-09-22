"""Fetch batch de contas de balanço (BPA/BPP) — sem TTM, valor pontual do período."""

from __future__ import annotations

import duckdb

from cvmdata.transform.account_map import ALL_BALANCE_CODES, get_component
from cvmdata.transform.indicators.models import Components, ReportingPeriod


def fetch_all_balance_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
    profiles: dict[str, str] | None = None,
) -> Components:
    """Batch query para BPA/BPP: retorna ``{ReportingPeriod: ComponentValues}``.

    Executa uma única query (UNION ALL de raw_bpa_clean + raw_bpp_clean) para
    todas as empresas/períodos. Contas de balanço não usam TTM — o valor é o
    saldo pontual do período.

    O perfil por CNPJ vem de ``company_classification`` (resolvido pelo step
    de classificação cadastral); CNPJs sem classificação persistem o mapeamento 
    ``default``.
    """
    filter_clause = "AND CNPJ_CIA = ?" if cnpj else ""

    params: list[object] = [ALL_BALANCE_CODES]
    if cnpj:
        params.append(cnpj)

    params.append(ALL_BALANCE_CODES)
    if cnpj:
        params.append(cnpj)

    rows = conn.execute(
        f"""
        SELECT CNPJ_CIA, DT_REFER::VARCHAR, CD_CONTA, DS_CONTA, VL_CONTA
        FROM (
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, DS_CONTA, VL_CONTA 
            FROM raw_bpa_clean
            WHERE CD_CONTA = ANY(?) {filter_clause}
            UNION ALL
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, DS_CONTA, VL_CONTA 
            FROM raw_bpp_clean
            WHERE CD_CONTA = ANY(?) {filter_clause}
        )
        """,
        params,
    ).fetchall()

    profiles = profiles or {}

    result: Components = {}
    for cnpj_r, dt_r, cd_conta, _ds_conta, vl_conta in rows:
        profile_id = profiles.get(cnpj_r, "default")
        name = get_component(cd_conta, profile_id)
        if name:
            valor = float(vl_conta) if vl_conta is not None else None
            period = ReportingPeriod(cnpj_r, dt_r)
            result.setdefault(period, {})[name] = valor

    return result