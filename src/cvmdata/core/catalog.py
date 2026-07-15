"""Catálogo central de datasets CVM processados pelo sistema.

Cada entrada no CATALOG define como identificar, extrair e carregar
um tipo de dado dos ZIPs da CVM (ITR/DFP).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class DatasetType(Enum):
    STATEMENT = auto()   # BPA, BPP, DRE — colunas financeiras + filtro CD_CONTA
    DIRECT_INSERT = auto()   # composicao_capital — INSERT direto sem filtro


@dataclass
class CvmDataset:
    pattern: str           # substring do nome do arquivo (lowercase)
    table: str             # nome da tabela no DuckDB
    type: DatasetType
    has_con_scope: bool = False  # se o nome contém "_con_"


CATALOG: dict[str, CvmDataset] = {
    "BPA": CvmDataset(
        pattern="bpa_con",
        table="raw_bpa",
        type=DatasetType.STATEMENT,
        has_con_scope=True,
    ),
    "BPP": CvmDataset(
        pattern="bpp_con",
        table="raw_bpp",
        type=DatasetType.STATEMENT,
        has_con_scope=True,
    ),
    "DRE": CvmDataset(
        pattern="dre_con",
        table="raw_dre",
        type=DatasetType.STATEMENT,
        has_con_scope=True,
    ),
    "COMPOSICAO_CAPITAL": CvmDataset(
        pattern="composicao_capital",
        table="composicao_capital",
        type=DatasetType.DIRECT_INSERT,
    ),
}

# Grupos de schema para DDL (apenas demonstrativos)
BALANCE_DEMOS: frozenset[str] = frozenset({"BPA", "BPP"})
FLOW_DEMOS: frozenset[str] = frozenset({"DRE"})
