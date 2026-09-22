from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, Sequence, TypeAlias


@dataclass(frozen=True, order=True)
class ReportingPeriod:
    """Chave de ``Components``: Identifica uma empresa/período (cnpj_cia, dt_refer)."""

    cnpj_cia: str
    dt_refer: str


# componente_semantico (ex.: 'patrimonio_liquido') -> valor em R$ (escala CVM)
ComponentValues: TypeAlias = dict[str, float | None]


# Período -> componentes calculados a partir dos demonstrativos
# Components = {
#     ReportingPeriod(cnpj_cia="33.000.167/0001-01", dt_refer="2024-09-30"): {
#         "patrimonio_liquido": 1000.0, 
#         "lucro_liquido": 500.0, 
#         ...
#     },
#     ...
# }
Components: TypeAlias = dict[ReportingPeriod, ComponentValues]


class IndicatorColumns(NamedTuple):
    """Colunas de ``indicators`` separadas para INSERT em batch (UNNEST)."""

    cnpjs: list[str]
    dt_refers: list[str]
    indicadores: list[str]
    valores: list[float | None]


@dataclass(frozen=True)
class IndicatorRow:
    """Uma linha de indicador no formato final — espelha a tabela ``indicators``
    
    IndicatorRow(cnpj_cia="33.000.167/0001-01", dt_refer="2024-09-30", indicador="roe", valor=50.0)
    """

    cnpj_cia: str
    dt_refer: str
    indicador: str
    valor: float | None

    @staticmethod
    def to_sql_columns(rows: Sequence[IndicatorRow]) -> IndicatorColumns:
        """Converte linhas nas colunas do INSERT em batch (UNNEST).

        Retorna um objeto nomeado cujos campos mapeiam diretamente as colunas de
        ``indicators``, pronto para passar ao ``unnest(?)`` de ``_persist_rows``.
        """
        cnpjs: list[str] = []
        dt_refers: list[str] = []
        indicadores: list[str] = []
        valores: list[float | None] = []

        for row in rows:
            cnpjs.append(row.cnpj_cia)
            dt_refers.append(row.dt_refer)
            indicadores.append(row.indicador)
            valores.append(row.valor)

        return IndicatorColumns(
            cnpjs=cnpjs,
            dt_refers=dt_refers,
            indicadores=indicadores,
            valores=valores,
        )