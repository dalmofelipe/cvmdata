"""Fetch batch de contas de balanço (BPA/BPP) — sem TTM, valor pontual do período."""

from __future__ import annotations

import duckdb

from cvmdata.ingestion.tables import TB_BPA_CLEAN, TB_BPP_CLEAN
from cvmdata.transform.account_map import (
    ALL_BALANCE_CODES,
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

    1. ``account_map`` pelo ``CD_CONTA`` e perfil — resolve o caso comum;
    2. se não resolveu, a linha é do BPP e o perfil não tem PL por código,
       ``text_map.resolve_pl`` pelo rótulo.

    O passo 2 existe porque o patrimônio líquido tem posição instável: 2.03 no
    layout padrão, 2.07/2.08 no financeiro, e 2.03 no financeiro significa ainda
    "Provisões" em 19 bancos e "Passivos Financeiros ao Custo Amortizado" em 16.
    Só o rótulo separa.

    A ordem importa. Como o ACCOUNT_MAP de ``banking`` não mapeia 2.03, uma
    linha "Provisões" cai no texto, não casa com o mapa de PL e é descartada.
    Invertido, "Provisões" entraria no patrimônio. E o passo 2 é desligado nos
    perfis que já resolvem PL por código — ver ``PL_BY_CODE_PROFILES``.

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
        if (
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