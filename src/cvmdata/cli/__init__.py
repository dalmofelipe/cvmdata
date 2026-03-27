# CLI package initialization
from . import handlers
from .cli import app
from .models import (
    DownloadInput,
    IndicatorsInput,
    LoadInput,
    NormalizeInput,
    Outcome,
    QueryInput,
    QueryResult,
)
from .models import (
    ClassifyCadInput,
    ClassifyCadResult,
    DownloadCadInput,
    DownloadInput,
    IndicatorsInput,
    LoadCadInput,
    LoadInput,
    NormalizeInput,
    Outcome,
    QueryCadInput,
    QueryCadResult,
    QueryInput,
    QueryResult,
)
from .render import render_outcome, render_query_result
from .render import render_outcome, render_query_cad_result, render_query_result

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
    # Cadastro command inputs/outputs
    "DownloadCadInput",
    "LoadCadInput",
    "ClassifyCadInput",
    "ClassifyCadResult",
    "QueryCadInput",
    "QueryCadResult",
    # Rendering
    "render_outcome",
        "render_query_cad_result",
    "render_query_result",
]




