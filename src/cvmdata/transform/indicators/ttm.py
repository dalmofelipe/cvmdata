"""TTM (Trailing Twelve Months) para contas de resultado (DRE).

Regra: ``YTD_atual + (FY_anterior - YTD_anterior_mesmo_periodo)``, com
fallback gradual quando os dados estão incompletos (ver ``_DRE_TTM_QUERY``
para a expressão completa em SQL).

``_DRE_TTM_QUERY`` é a ÚNICA fonte de verdade da regra de TTM. Tanto o
caminho batch (``_fetch_all_dre_components``, usado em produção) quanto o
single-row (``_get_ttm_value``, usado em debug e nos testes unitários de
fallback) rodam a mesma query — o segundo é só um wrapper que filtra o
resultado do primeiro para uma única conta/período.
"""

from __future__ import annotations

import duckdb

from cvmdata.transform.account_map import ACCOUNT_MAP, get_component
from cvmdata.transform.indicators.models import Components


# Fórmula TTM completa, com fallback gradual, expressa em SQL:
#   1. Sem YTD atual   -> retorna FY anterior (ou NULL)
#   2. Sem FY anterior -> retorna YTD atual (proxy parcial)
#   3. Sem PENÚLTIMO   -> retorna FY anterior (proxy sem ajuste)
#   4. Todos presentes -> YTD_atual + (FY_anterior - PENÚLTIMO)
_DRE_TTM_QUERY = """
WITH periods AS (
    SELECT DISTINCT CNPJ_CIA, DT_REFER
    FROM raw_dre_clean
    WHERE CD_CONTA IN ({placeholders}) AND ORDEM_EXERC = 'ÚLTIMO' {filter_clause}
),
dfp_periods AS (
    SELECT DISTINCT CNPJ_CIA, DT_REFER AS fy_dt_refer, DT_FIM_EXERC
    FROM raw_dre_clean
    WHERE source = 'dfp' AND ORDEM_EXERC = 'ÚLTIMO'
),
fy_ref AS (
    SELECT p.CNPJ_CIA, p.DT_REFER, d.fy_dt_refer
    FROM periods p
    LEFT JOIN dfp_periods d
      ON d.CNPJ_CIA = p.CNPJ_CIA AND d.DT_FIM_EXERC < p.DT_REFER
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY p.CNPJ_CIA, p.DT_REFER
        ORDER BY d.DT_FIM_EXERC DESC
    ) = 1
),
accounts AS (
    SELECT DISTINCT CD_CONTA FROM raw_dre_clean
    WHERE CD_CONTA IN ({placeholders})
),
grid AS (
    SELECT fy_ref.*, a.CD_CONTA
    FROM fy_ref CROSS JOIN accounts a
)
SELECT
    g.CNPJ_CIA,
    g.DT_REFER::VARCHAR,
    g.CD_CONTA,
    CASE
        WHEN ytd.VL_CONTA IS NULL THEN fy.VL_CONTA
        WHEN fy.VL_CONTA  IS NULL THEN ytd.VL_CONTA
        WHEN penu.VL_CONTA IS NULL THEN fy.VL_CONTA
        ELSE ytd.VL_CONTA + (fy.VL_CONTA - penu.VL_CONTA)
    END AS ttm_valor
FROM grid g
LEFT JOIN raw_dre_clean ytd
    ON ytd.CNPJ_CIA = g.CNPJ_CIA 
    AND ytd.DT_REFER = g.DT_REFER
    AND ytd.CD_CONTA = g.CD_CONTA 
    AND ytd.ORDEM_EXERC = 'ÚLTIMO'
LEFT JOIN raw_dre_clean penu
    ON penu.CNPJ_CIA = g.CNPJ_CIA 
    AND penu.DT_REFER = g.DT_REFER
    AND penu.CD_CONTA = g.CD_CONTA 
    AND penu.ORDEM_EXERC = 'PENÚLTIMO'
LEFT JOIN raw_dre_clean fy
    ON fy.CNPJ_CIA = g.CNPJ_CIA 
    AND fy.DT_REFER = g.fy_dt_refer
    AND fy.CD_CONTA = g.CD_CONTA 
    AND fy.ORDEM_EXERC = 'ÚLTIMO'
ORDER BY g.CNPJ_CIA, g.DT_REFER, g.CD_CONTA
"""


def _fetch_all_dre_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> Components:
    """Batch: calcula o TTM de todas as contas DRE em uma única query.

    O join/CASE que resolve o TTM roda inteiro no DuckDB (ver
    ``_DRE_TTM_QUERY``) — este código só agrupa o resultado por
    (cnpj, dt_refer) e traduz CD_CONTA -> componente semântico.

    Returns:
        ``{(cnpj, dt_refer): {componente_semantico: valor_ttm}}``
    """
    dre_codes = [code for code in ACCOUNT_MAP if code.startswith("3.")]
    placeholders = ", ".join(f"'{code}'" for code in dre_codes)
    filter_clause = "AND CNPJ_CIA = ?" if cnpj else ""
    params: list[str] = [cnpj] if cnpj else []

    query = _DRE_TTM_QUERY.format(placeholders=placeholders, filter_clause=filter_clause)
    rows = conn.execute(query, params).fetchall()

    result: Components = {}
    for cnpj_r, dt_r, cd_conta, ttm_valor in rows:
        name = get_component(cd_conta)
        if name:
            # VL_CONTA é DECIMAL no schema -> o driver retorna decimal.Decimal.
            # Cast explícito pra float, senão o Decimal se mistura com float
            # em calc_plan.py (ex: roe faz Decimal / float -> TypeError).
            valor = float(ttm_valor) if ttm_valor is not None else None
            result.setdefault((cnpj_r, dt_r), {})[name] = valor
    return result


def _get_ttm_value(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str,
    dt_refer: str,
    cd_conta: str,
) -> float | None:
    """Retorna o valor TTM de uma única conta DRE — wrapper de debug/teste.

    Roda a MESMA query batch (``_fetch_all_dre_components``), filtrada
    para uma empresa, e extrai o valor de uma única conta/período. Não
    existe lógica de fallback duplicada aqui — é só um recorte do
    resultado da fonte única de verdade.

    Não usar em loop sobre muitos pares (empresa, período): cada chamada
    roda a query inteira para a empresa. Para processar em lote, chame
    ``_fetch_all_dre_components`` diretamente.

    Args:
        conn:     Conexão DuckDB com ``raw_dre_clean`` já populado.
        cnpj:     CNPJ da empresa (ex: ``"33.000.167/0001-01"``).
        dt_refer: Data de referência do período (ex: ``"2024-09-30"``).
        cd_conta: Código da conta CVM (ex: ``"3.01"``).

    Returns:
        Valor TTM como float, ou None se dados insuficientes.
    """
    name = get_component(cd_conta)
    if name is None:
        return None
    components = _fetch_all_dre_components(conn, cnpj)
    return components.get((cnpj, dt_refer), {}).get(name)
