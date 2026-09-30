"""Nomes canônicos das tabelas DuckDB — fonte única de verdade.

Famílias:

- ``raw_*`` — dados brutos como publicados pela CVM. Declarados em
  ``catalog.CATALOG`` (campo ``CvmDataset.table``), não aqui;
- ``*_clean`` — dados normalizados/deduplicados, derivados de ``raw_*`` por
  :func:`clean_table_name`;
- cadastrais e derivadas — declaradas abaixo.

Regra de uso: SQL e dados estruturados referenciam estas constantes. O literal
fica no sítio de declaração — o ``CREATE TABLE`` em ``ingestion/database.py`` e
o catálogo. Docstrings e mensagens de log mantêm o nome por extenso, porque são
prosa, não referência.
"""

from __future__ import annotations

RAW_PREFIX = "raw_"
CLEAN_SUFFIX = "_clean"

BPA_CLEAN = "bpa_clean"
BPP_CLEAN = "bpp_clean"
DRE_CLEAN = "dre_clean"

CLEAN_TABLES: tuple[str, ...] = (BPA_CLEAN, BPP_CLEAN, DRE_CLEAN)
BALANCE_CLEAN_TABLES: frozenset[str] = frozenset({BPA_CLEAN, BPP_CLEAN})

# ── Cadastrais ────────────────────────────────────────────────────────────────

CAD_CIA_ABERTA_RAW = "cad_cia_aberta_raw"
COMPANY_CLASSIFICATION = "company_classification"
CLASSIFICATION_CURATION_EVENTS = "classification_curation_events"
SETOR_PROFILE_MAP = "setor_profile_map"

# ── Derivadas ─────────────────────────────────────────────────────────────────

INDICATORS = "indicators"
B3_TICKERS = "b3_tickers"
COMPOSICAO_CAPITAL = "composicao_capital"


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
