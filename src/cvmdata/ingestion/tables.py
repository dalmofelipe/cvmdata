"""Nomes canônicos das tabelas DuckDB — fonte única de verdade.

Convenção de nomenclatura:

- ``raw_*`` — dados brutos como publicados pela CVM (``raw_bpa``, ``raw_bpp``, ``raw_dre``);
- ``*_clean`` — dados normalizados/deduplicados, derivados de ``raw_*`` 
    (``bpa_clean``, ``bpp_clean``, ``dre_clean``);
"""

from __future__ import annotations

RAW_PREFIX = "raw_"
CLEAN_SUFFIX = "_clean"

BPA_CLEAN = "bpa_clean"
BPP_CLEAN = "bpp_clean"
DRE_CLEAN = "dre_clean"

CLEAN_TABLES: tuple[str, ...] = (BPA_CLEAN, BPP_CLEAN, DRE_CLEAN)
BALANCE_CLEAN_TABLES: frozenset[str] = frozenset({BPA_CLEAN, BPP_CLEAN})


def clean_table_name(raw_table: str) -> str:
    """Deriva o nome da tabela normalizada a partir do nome da tabela bruta.

    Args:
        raw_table: Nome da tabela de origem (ex: ``raw_bpa``).

    Returns:
        Nome da tabela normalizada (ex: ``bpa_clean``).

    Raises:
        ValueError: Se ``raw_table`` não tiver o prefixo ``raw_``, ou se o
            prefixo não deixar nenhum nome de demonstrativo. 
            Sem essa validação, ``"bpa"`` produziria ``"bpa_clean"`` 
            silenciosamente e ``"raw_"`` produziria ``"_clean"``.
    """
    name = raw_table.removeprefix(RAW_PREFIX)
    if name == raw_table or not name:
        raise ValueError(
            f"clean_table_name: '{raw_table}' não é uma tabela raw_* "
            f"(esperado prefixo '{RAW_PREFIX}', ex: 'raw_bpa')"
        )
    return f"{name}{CLEAN_SUFFIX}"
