"""Cálculo de indicadores fundamentalistas: fetch batch + TTM + orquestração.

Este pacote substitui o antigo módulo único ``indicators.py``, quebrado em:

- ``ttm``:      TTM de contas DRE (fórmula pura + batch em SQL)
- ``balance``:  fetch batch de contas de balanço (BPA/BPP), sem TTM
- ``indicator_rows``:    construção das linhas de indicador via ``CALC_PLAN``
- ``calculate_all``: orquestração (fetch -> cálculo -> persistência)
"""

from cvmdata.transform.indicators.calculate_all import calculate_all
from cvmdata.transform.indicators.ttm import _get_ttm_value

__all__ = ["calculate_all", "_get_ttm_value"]
