# Handlers subpackage initialization
from . import classify_cad, download, download_cad, indicators, load, load_cad, normalize, query, query_cad

__all__ = [
    # Data pipeline
    "download",
    "load",
    "normalize",
    "indicators",
    "query",
    # Cadastro
    "download_cad",
    "load_cad",
    "classify_cad",
    "query_cad",
]

