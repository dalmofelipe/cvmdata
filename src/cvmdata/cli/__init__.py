# CLI package initialization
from . import handlers
from .cli import app
from .models import (
    ClassifyInfoCadInput,
    ClassifyInfoCadResult,
    DownloadInfoCadInput,
    DownloadInput,
    IndicatorsInput,
    LoadInfoCadInput,
    LoadInput,
    NormalizeInput,
    Outcome,
    QueryInfoCadInput,
    QueryInfoCadResult,
    QueryInput,
    QueryResult,
)
from .render import render_outcome, render_query_info_cad_result, render_query_result

__all__ = [
    "app",
    "handlers",
    # Outcome
    "Outcome",
    # Data command inputs/outputs
    "DownloadInput",
    "LoadInput",
    "NormalizeInput",
    "IndicatorsInput",
    "QueryInput",
    "QueryResult",
    # Informação Cadastral command inputs/outputs
    "DownloadInfoCadInput",
    "LoadInfoCadInput",
    "ClassifyInfoCadInput",
    "ClassifyInfoCadResult",
    "QueryInfoCadInput",
    "QueryInfoCadResult",
    # Rendering
    "render_outcome",
    "render_query_info_cad_result",
    "render_query_result",
]
