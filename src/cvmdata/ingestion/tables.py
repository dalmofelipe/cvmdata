"""Nomes canônicos das tabelas DuckDB — fonte única de verdade.

Referência: docs/tabelas.md
"""

from __future__ import annotations

RAW_PREFIX = "raw_"
CLEAN_SUFFIX = "_clean"

TB_BPA_CLEAN = "bpa_clean"
TB_BPP_CLEAN = "bpp_clean"
TB_DRE_CLEAN = "dre_clean"

CLEAN_TABLES: tuple[str, ...] = (TB_BPA_CLEAN, TB_BPP_CLEAN, TB_DRE_CLEAN)
BALANCE_CLEAN_TABLES: frozenset[str] = frozenset({TB_BPA_CLEAN, TB_BPP_CLEAN})

# ── Cadastrais ────────────────────────────────────────────────────────────────

TB_CAD_CIA_ABERTA_RAW = "cad_cia_aberta_raw"
TB_COMPANY_CLASSIFICATION = "company_classification"

# ── Derivadas ─────────────────────────────────────────────────────────────────

TB_INDICATORS = "indicators"
TB_B3_TICKERS = "b3_tickers"
TB_COMPOSICAO_CAPITAL = "composicao_capital"


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
