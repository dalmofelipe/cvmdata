"""Compara indicadores do cvmdata com plataformas externas.

Adicione uma empresa em ``REPORT_COMPANY.companies`` usando ``Company`` e uma
plataforma em ``Company.platforms`` com um dicionário
``{Period: [Indicator, ...]}``. O relatório é exibido no terminal e salvo em
``scripts/report.csv``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import duckdb
from rich.console import Console
from rich.table import Table

from cvmdata.config import settings
from cvmdata.ingestion.tables import TB_COMPANY_CLASSIFICATION, TB_INDICATORS
from cvmdata.transform.calc_plan import CALC_PLAN

TOLERANCE: float = 0.05
REPORT_PATH = Path(__file__).with_name("report.csv")


@dataclass(frozen=True, order=True)
class Period:
    year: int
    month: int

    def __post_init__(self) -> None:
        if self.year not in range(2011, 2027):
            raise ValueError("year deve estar entre 2011 e 2026")
        if self.month not in range(1, 13):
            raise ValueError("month deve estar entre 1 e 12")

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True)
class Indicator:
    name: str
    value: float | None


PlatformIndicators: TypeAlias = dict[Period, list[Indicator]]


@dataclass(frozen=True)
class Company:
    cnpj: str
    platforms: dict[str, PlatformIndicators]


@dataclass(frozen=True)
class ReportCompany:
    companies: list[Company]


# ITAÚ UNIBANCO (banking) -------------------------------------------


STATUS_INVEST_CVM_ITUB_CNPJ = "60.872.504/0001-23"
STATUS_INVEST_CVM_ITUB_INDICATORS: PlatformIndicators = {
    Period(2026, 6): [
        Indicator("divida_liquida_pl", None),
        Indicator("giro_ativo", 0.12),
        Indicator("margem_bruta", 37.23),
        Indicator("margem_ebit", 14.17),
        Indicator("margem_liquida", 12.13),
        Indicator("liquidez_corrente", 0.12),
        Indicator("roa", 1.46),
        Indicator("roe", 21.50),
        Indicator("roic", None),
    ],
    Period(2025, 12): [
        Indicator("divida_liquida_pl", None),
        Indicator("giro_ativo", 0.13),
        Indicator("margem_bruta", 35.89),
        Indicator("margem_ebit", 12.98),
        Indicator("margem_liquida", 11.59),
        Indicator("liquidez_corrente", 0.14),
        Indicator("roa", 1.46),
        Indicator("roe", 21.93),
        Indicator("roic", None),
    ],
}


# PETROBRAS (default) -------------------------------------------


DADOS_DE_MERCADO_CVM_PETR_CNPJ = "33.000.167/0001-01"
DADOS_DE_MERCADO_CVM_PETR_INDICATORS: PlatformIndicators = {
    Period(2026, 6): [
        Indicator("capital_giro", -26401 * 1_000_000),
        Indicator("divida_bruta", 366533 * 1_000_000),
        Indicator("divida_liquida", 312769 * 1_000_000),
        Indicator("endividamento_pl", 165.44),
        Indicator("giro_ativo", 0.43),
        Indicator("margem_bruta", 50.60),
        Indicator("margem_ebit", 33.86),
        Indicator("margem_liquida", 24.39),
        Indicator("liquidez_corrente", 0.85),
        Indicator("liquidez_seca", 0.58),
        Indicator("liquidez_imediata", 0.18),
        Indicator("roa", 0.10 * 100), # A dados de mercado é unica que calcula ROA com valor decimal.
        Indicator("roe", 27.76),
        Indicator("roic", 15.60),
    ],
    Period(2025, 12): [
        Indicator("capital_giro", -58342 * 1_000_000),
        Indicator("divida_bruta", 384025 * 1_000_000),
        Indicator("divida_liquida", 333417 * 1_000_000),
        Indicator("endividamento_pl", 192.97),
        Indicator("giro_ativo", 0.41),
        Indicator("margem_bruta", 47.63),
        Indicator("margem_ebit", 29.27),
        Indicator("margem_liquida", 22.23),
        Indicator("liquidez_corrente", 0.71),
        Indicator("liquidez_seca", 0.48),
        Indicator("liquidez_imediata", 0.18),
        Indicator("roa", 0.09 * 100),
        Indicator("roe", 26.49),
        Indicator("roic", 12.87),
    ],
}


REPORT_COMPANY = ReportCompany(
    companies=[
        Company(
            cnpj=STATUS_INVEST_CVM_ITUB_CNPJ,
            platforms={"Status Invest": STATUS_INVEST_CVM_ITUB_INDICATORS},
        ),
        Company(
            cnpj=DADOS_DE_MERCADO_CVM_PETR_CNPJ,
            platforms={"Dados de Mercado": DADOS_DE_MERCADO_CVM_PETR_INDICATORS},
        ),
    ]
)


def _indicator_names(platforms: dict[str, PlatformIndicators]) -> list[str]:
    configured = {
        indicator.name
        for periods in platforms.values()
        for indicators in periods.values()
        for indicator in indicators
    }
    formalized = [name for name, _, _ in CALC_PLAN]
    return [name for name in formalized if name in configured] + sorted(
        configured.difference(formalized)
    )


def _fetch_company(
    conn: duckdb.DuckDBPyConnection, cnpj: str
) -> tuple[str, str | None, str | None]:
    query = f"""
        SELECT cnpj_cia,
               COALESCE(NULLIF(denom_comerc, ''), denom_social),
               profile_id
        FROM {TB_COMPANY_CLASSIFICATION}
        WHERE cnpj_cia = ?
    """
    row = conn.execute(query, [cnpj]).fetchone()
    if row is None:
        return cnpj, None, None
    return row[0], row[1], row[2]


def _fetch_cvm_values(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str,
    periods: set[Period],
    indicator_names: list[str],
) -> dict[tuple[Period, str], float | None]:
    if not periods or not indicator_names:
        return {}

    period_prefixes = sorted(str(period) for period in periods)
    period_placeholders = ", ".join("?" for _ in period_prefixes)
    indicator_placeholders = ", ".join("?" for _ in indicator_names)
    query = f"""
        SELECT LEFT(CAST(dt_refer AS VARCHAR), 7), indicador, valor
        FROM {TB_INDICATORS}
        WHERE cnpj_cia = ?
          AND LEFT(CAST(dt_refer AS VARCHAR), 7) IN ({period_placeholders})
          AND indicador IN ({indicator_placeholders})
    """
    params = [cnpj, *period_prefixes, *indicator_names]
    rows = conn.execute(query, params).fetchall()
    return {
        (Period(int(period[:4]), int(period[5:7])), indicator): value
        for period, indicator, value in rows
    }


def _deviation(cvm_value: float | None, external_value: float | None) -> float | None:
    if cvm_value is None or external_value is None or external_value == 0:
        return None
    cvm_value = round(cvm_value, 2)
    external_value = round(external_value, 2)
    if external_value == 0:
        return None
    return (cvm_value - external_value) / abs(external_value)


def _format_value(value: float | None) -> str:
    return "--" if value is None else f"{value:.2f}"


def _format_indicator_value(indicator: str, value: float | None) -> str:
    if value is None:
        return "--"
    if indicator not in {"capital_giro", "divida_bruta", "divida_liquida"}:
        return _format_value(value)

    formatted = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


def _format_deviation(value: float | None) -> str:
    return "--" if value is None else f"{value:+.2%}"


def _build_company_report(company: Company) -> list[dict[str, object]]:
    """Busca os valores do cvmdata e produz as linhas do relatório."""
    periods = {
        period
        for platform in company.platforms.values()
        for period in platform
    }
    names = _indicator_names(company.platforms)

    with duckdb.connect(str(settings.db_path), read_only=True) as conn:
        _, company_name, profile = _fetch_company(conn, company.cnpj)
        cvm_values = _fetch_cvm_values(conn, company.cnpj, periods, names)

    rows: list[dict[str, object]] = []
    for platform_name, platform_periods in company.platforms.items():
        platform_names = _indicator_names({platform_name: platform_periods})
        for period in sorted(platform_periods):
            external_values = {
                indicator.name: indicator.value
                for indicator in platform_periods[period]
            }
            for name in platform_names:
                external_value = external_values.get(name)
                cvm_value = cvm_values.get((period, name))
                cvm_value = round(cvm_value, 2) if cvm_value is not None else None
                external_value = (
                    round(external_value, 2) if external_value is not None else None
                )
                deviation = _deviation(cvm_value, external_value)
                rows.append(
                    {
                        "cnpj": company.cnpj,
                        "empresa": company_name,
                        "perfil": profile,
                        "plataforma": platform_name,
                        "periodo": str(period),
                        "indicador": name,
                        "cvmdata": cvm_value,
                        "plataforma_valor": external_value,
                        "desvio": deviation,
                        "fora_tolerancia": deviation is not None
                        and abs(deviation) > TOLERANCE,
                    }
                )
    return rows


def build_report(report: ReportCompany) -> list[dict[str, object]]:
    """Busca os valores do cvmdata para todas as empresas configuradas."""
    return [
        row
        for company in report.companies
        for row in _build_company_report(company)
    ]


def write_csv(rows: list[dict[str, object]], path: Path = REPORT_PATH) -> None:
    fields = [
        "cnpj",
        "empresa",
        "perfil",
        "plataforma",
        "periodo",
        "indicador",
        "cvmdata",
        "plataforma_valor",
        "desvio",
        "fora_tolerancia",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            csv_row = row.copy()
            csv_row["desvio"] = _format_deviation(row["desvio"])
            csv_row["cvmdata"] = _format_indicator_value(
                str(row["indicador"]), row["cvmdata"]
            )
            csv_row["plataforma_valor"] = _format_indicator_value(
                str(row["indicador"]), row["plataforma_valor"]
            )
            writer.writerow(csv_row)


def render_report(rows: list[dict[str, object]]) -> Table:
    table = Table(title="Comparação de indicadores")
    table.add_column("Empresa")
    table.add_column("Período")
    table.add_column("Plataforma")
    table.add_column("Indicador")
    table.add_column("CVMData", justify="right")
    table.add_column("Externo", justify="right")
    table.add_column("Desvio", justify="right")

    for row in rows:
        deviation = row["desvio"]
        deviation_text = _format_deviation(deviation)
        cvm_text = _format_indicator_value(str(row["indicador"]), row["cvmdata"])
        if row["fora_tolerancia"]:
            cvm_text = f"[red]{cvm_text}[/red]"
            deviation_text = f"[red]{deviation_text}[/red]"
        table.add_row(
            str(row["empresa"] or "--"),
            str(row["periodo"]),
            str(row["plataforma"]),
            str(row["indicador"]),
            cvm_text,
            _format_indicator_value(str(row["indicador"]), row["plataforma_valor"]),
            deviation_text,
        )
    return table


def main() -> None:
    if not settings.db_path.exists():
        raise FileNotFoundError(f"Banco não encontrado: {settings.db_path}")
    if not 0 <= TOLERANCE:
        raise ValueError("TOLERANCE deve ser maior ou igual a zero")

    rows = build_report(REPORT_COMPANY)
    write_csv(rows)
    Console().print(render_report(rows))
    Console().print(f"CSV salvo em {REPORT_PATH}")


if __name__ == "__main__":
    main()
