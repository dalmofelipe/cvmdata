"""Classificação cadastral de empresas por layout contábil.

API pública: :func:`classify_info_cad`. Os módulos internos são
:mod:`~cvmdata.transform.info_cad.classify` (orquestração),
:mod:`~cvmdata.transform.info_cad.queries` (composição de SQL),
:mod:`~cvmdata.transform.info_cad.repository` (leitura das fontes) e
:mod:`~cvmdata.transform.info_cad.models` (contrato).
"""

from __future__ import annotations

from cvmdata.transform.info_cad.classify import classify_info_cad
from cvmdata.transform.info_cad.models import (
    ClassificationCounts,
    MissingCleanTablesError,
)

__all__ = [
    "ClassificationCounts",
    "MissingCleanTablesError",
    "classify_info_cad",
]