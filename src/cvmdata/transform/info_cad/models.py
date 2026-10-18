"""Contrato de retorno da classificação."""

from __future__ import annotations

from typing import TypedDict


class ClassificationCounts(TypedDict):
    """Métricas de :func:`cvmdata.transform.info_cad.classify_info_cad`."""

    total: int
    by_profile: dict[str, int]
    by_rule: dict[str, int]


class MissingCleanTablesError(RuntimeError):
    """Uma ou mais ``*_clean`` não existem — o universo está incompleto."""


class MissingCadCiaAbertaTableError(RuntimeError):
    """``cad_cia_aberta_raw`` não existe — a classificação perderia os descritores."""
