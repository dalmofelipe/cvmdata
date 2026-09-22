from __future__ import annotations

from cvmdata.transform.calc_plan import (
    CALC_PLAN,
    calc_divida_liquida_pl,
    calc_roic,
)
from cvmdata.transform.indicators.models import ComponentValues, IndicatorRow


def build_indicator_rows(
    cnpj_cia: str,
    dt_refer: str,
    comp: ComponentValues,
) -> list[IndicatorRow]:
    """Calcula os indicadores de ``CALC_PLAN`` para um par (cnpj_cia, dt_refer)."""
    
    rows: list[IndicatorRow] = []

    for indicator_name, fn, arg_names in CALC_PLAN:
        if indicator_name == "divida_liquida_pl":
            valor = calc_divida_liquida_pl(comp)
        elif indicator_name == "roic":
            valor = calc_roic(comp)
        else:
            args = [comp.get(a) for a in arg_names]
            valor = fn(*args)  # type: ignore[operator]
        rows.append(IndicatorRow(cnpj_cia, dt_refer, indicator_name, valor))

    return rows
