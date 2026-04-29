# Handlers subpackage initialization
from .transform import classify_info_cad, download_info_cad, load_info_cad, query_info_cad

from .ingestion import download, indicators, load, normalize, query

__all__ = [
    # Data pipeline
    "download",
    "load",
    "normalize",
    "indicators",
    "query",
    # Informação cadastral
    "download_info_cad",
    "load_info_cad",
    "classify_info_cad",
    "query_info_cad",
]

