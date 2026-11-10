"""Fetch batch de contas de balanço (BPA/BPP) — sem TTM, valor pontual do período."""

from __future__ import annotations

import duckdb

from cvmdata.ingestion.tables import TB_BPA_CLEAN, TB_BPP_CLEAN
from cvmdata.transform.account_map import (
    ALL_BALANCE_CODES,
    BPP_PL_CODES,
    PL_BY_CODE_PROFILES,
    get_component,
)
from cvmdata.transform.indicators.models import Components, ReportingPeriod
from cvmdata.transform.text_map import resolve_pl


def fetch_all_balance_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
    profiles: dict[str, str] | None = None,
) -> Components:
    """Batch query para BPA/BPP: retorna ``{ReportingPeriod: ComponentValues}``.

    Executa uma única query (UNION ALL de bpa_clean + bpp_clean) para
    todas as empresas/períodos. Contas de balanço não usam TTM — o valor é o
    saldo pontual do período.

    Cada conta passa por duas tentativas, nesta ordem:

    1. ``account_map`` pelo ``CD_CONTA`` e perfil — resolve o caso padrão/default;
    2. Se não resolveu, a linha é do BPP e o perfil não tem PL por código, então tenta
       resolver por texto via  ``text_map.resolve_pl``.

    Referências: docs/account_map.md, docs/text_map.md, docs/baking_profile.md
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
        SELECT CNPJ_CIA, DT_REFER::VARCHAR, CD_CONTA, DS_CONTA, VL_CONTA, origem
        FROM (
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, DS_CONTA, VL_CONTA, 'bpa' AS origem
            FROM {TB_BPA_CLEAN}
            WHERE CD_CONTA = ANY(?) {filter_clause}
            UNION ALL
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, DS_CONTA, VL_CONTA, 'bpp' AS origem
            FROM {TB_BPP_CLEAN}
            WHERE CD_CONTA = ANY(?) {filter_clause}
        )
        """,
        params,
    ).fetchall()

    profiles = profiles or {}

    result: Components = {}
    for cnpj_r, dt_r, cd_conta, ds_conta, vl_conta, origem in rows:
        profile_id = profiles.get(cnpj_r, "default")
        name = get_component(cd_conta, profile_id)
        if origem == "bpp" and cd_conta in BPP_PL_CODES and ds_conta is not None:
            name = resolve_pl(ds_conta, cd_conta)
        elif (
            name is None
            and origem == "bpp"
            and ds_conta is not None
            and profile_id not in PL_BY_CODE_PROFILES
        ):
            name = resolve_pl(ds_conta, cd_conta)
        if name:
            valor = float(vl_conta) if vl_conta is not None else None
            period = ReportingPeriod(cnpj_r, dt_r)
            result.setdefault(period, {})[name] = valor

    return result