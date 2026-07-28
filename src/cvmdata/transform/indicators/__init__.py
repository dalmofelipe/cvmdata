"""Cálculo de indicadores fundamentalistas: fetch batch + TTM + orquestração.

Este pacote substitui o antigo módulo único ``indicators.py``, quebrado em:

- ``ttm``:      TTM de contas DRE (fórmula pura + batch em SQL)
- ``balance``:  fetch batch de contas de balanço (BPA/BPP), sem TTM
- ``build``:    construção das linhas de indicador via ``CALC_PLAN``
- ``pipeline``: orquestração (fetch -> cálculo -> persistência)

``calculate_all`` e ``_get_ttm_value`` continuam importáveis diretamente de
``cvmdata.transform.indicators`` — nenhum import existente quebra.
"""

from cvmdata.transform.indicators.pipeline import calculate_all
from cvmdata.transform.indicators.ttm import _get_ttm_value

__all__ = ["calculate_all", "_get_ttm_value"]
