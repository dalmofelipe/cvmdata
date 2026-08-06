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
WITH dre_wide AS MATERIALIZED (
    SELECT
        CNPJ_CIA,
        DT_REFER,
        CD_CONTA,
        source,
        MAX(CASE WHEN ORDEM_EXERC = 'ÚLTIMO' THEN DT_FIM_EXERC END) AS fy_dt_fim_exerc,
        MAX(CASE WHEN ORDEM_EXERC = 'ÚLTIMO' THEN VL_CONTA END) AS ultimo_val,
        MAX(CASE WHEN ORDEM_EXERC = 'PENÚLTIMO' THEN VL_CONTA END) AS penultimo_val
    FROM raw_dre_clean
    WHERE CD_CONTA = ANY(?) {filter_clause}
    GROUP BY CNPJ_CIA, DT_REFER, CD_CONTA, source
),
periods AS (
    SELECT DISTINCT CNPJ_CIA, DT_REFER
    FROM dre_wide
    WHERE ultimo_val IS NOT NULL
),
dfp_periods AS (
    SELECT DISTINCT CNPJ_CIA, DT_REFER AS fy_dt_refer, fy_dt_fim_exerc AS DT_FIM_EXERC
    FROM dre_wide
    WHERE source = 'dfp' AND ultimo_val IS NOT NULL
),
fy_ref AS (
    SELECT p.CNPJ_CIA, p.DT_REFER, d.fy_dt_refer
    FROM periods p
    ASOF LEFT JOIN dfp_periods d
      ON d.CNPJ_CIA = p.CNPJ_CIA AND d.DT_FIM_EXERC < p.DT_REFER
),
accounts(CD_CONTA) AS (
    SELECT UNNEST(?)
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
        WHEN current.ultimo_val IS NULL THEN fy.ultimo_val
        WHEN fy.ultimo_val  IS NULL THEN current.ultimo_val
        WHEN current.penultimo_val IS NULL THEN fy.ultimo_val
        ELSE current.ultimo_val + (fy.ultimo_val - current.penultimo_val)
    END AS ttm_valor
FROM grid g
LEFT JOIN dre_wide current
    ON current.CNPJ_CIA = g.CNPJ_CIA
    AND current.DT_REFER = g.DT_REFER
    AND current.CD_CONTA = g.CD_CONTA
LEFT JOIN dre_wide fy
    ON fy.CNPJ_CIA = g.CNPJ_CIA
    AND fy.DT_REFER = g.fy_dt_refer
    AND fy.CD_CONTA = g.CD_CONTA
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
    filter_clause = "AND CNPJ_CIA = ?" if cnpj else ""

    query = _DRE_TTM_QUERY.format(filter_clause=filter_clause)

    params: list[object] = [dre_codes]
    if cnpj:
        params.append(cnpj)
    params.append(dre_codes)

    rows = conn.execute(query, params).fetchall()

    result: Components = {}
    for cnpj_r, dt_r, cd_conta, ttm_valor in rows:
        name = get_component(cd_conta)
        if name:
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
