"""Typer CLI wiring.

A CLI expõe apenas comandos de consulta e um único comando de orquestração do
pipeline completo.
"""

from __future__ import annotations

from typing import Optional

import typer

from cvmdata.cli import handlers, logging, models, render
from cvmdata.cli.constants import (
    INDICATORS_YEAR_MAX,
    INDICATORS_YEAR_MIN,
    INFO_CAD_PAGE_SIZE_DEFAULT,
    INFO_CAD_PAGE_SIZE_MAX,
    INFO_CAD_PAGE_SIZE_MIN,
)
from cvmdata.config import settings
from cvmdata.pipeline import PipelineExecutionError, YearsParseError, parse_years, run_full
from cvmdata.pipeline import models as pipeline_models

app = typer.Typer(
    name="cvmdata",
    no_args_is_help=True,
)

pipeline_app = typer.Typer(
    help="Executa o pipeline completo (financeiro + cadastral).",
    no_args_is_help=True,
)

app.add_typer(pipeline_app, name="pipeline")


def _render_pipeline_report(report: pipeline_models.PipelineReport) -> None:
    typer.echo(f"Pipeline '{report.name}': {report.status}")
    for step in report.steps:
        msg = f" — {step.message}" if step.message else ""
        typer.echo(f"- {step.name}: {step.status}{msg}")


@pipeline_app.command("run")
def pipeline_run(
    years: Optional[str] = typer.Option(
        None,
        "--years",
        help="Ano, lista ou intervalo (ex: 2024 | 2021,2022,2024 | 2021:2025).",
    ),
    force_download: bool = typer.Option(
        False,
        "--force-download",
        help="Re-baixa mesmo se ZIP/arquivos já existirem.",
    ),
    cnpj: Optional[str] = typer.Option(
        None,
        "--cnpj",
        help="Filtra o cálculo de indicadores por CNPJ (opcional).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Executa o pipeline full (financeiro + cadastral)."""
    logging.configure_logging(verbose)

    try:
        years_list = parse_years(years) if years else list(settings.years)
        report = run_full(years=years_list, force_download=force_download, cnpj=cnpj)
        _render_pipeline_report(report)
        raise typer.Exit(0)
    except YearsParseError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1)
    except PipelineExecutionError as exc:
        if exc.report is not None:
            _render_pipeline_report(exc.report)
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1)


# ============================================================================
# Indicators (consulta)
# ============================================================================


@app.command("indicators")
def indicators(
    cnpj: str = typer.Option(..., "--cnpj", help="CNPJ da empresa (ex: 00.000.000/0001-00)."),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Filtrar por ano (ex: 2024)."),
) -> None:
    """Consulta indicadores fundamentalistas calculados (por CNPJ)."""
    if year is not None and not (INDICATORS_YEAR_MIN <= year <= INDICATORS_YEAR_MAX):
        typer.echo(
            f"✗ Ano inválido (deve estar entre {INDICATORS_YEAR_MIN} e {INDICATORS_YEAR_MAX})",
            err=True,
        )
        raise typer.Exit(1)

    inp = models.IndicatorsInput(cnpj=cnpj, year=year)
    outcome = handlers.indicators(inp)
    render.render_indicators_result(outcome)


# ============================================================================
@app.command("info-cad")
def info_cad(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="CNPJ da empresa (ex: 12.345.678/0001-99)."
    ),
    page: int = typer.Option(
        1, "--page", help="Página do resumo (>= 1)."
    ),
    page_size: int = typer.Option(
        INFO_CAD_PAGE_SIZE_DEFAULT,
        "--page-size",
        help="Tamanho da página do resumo (entre 20 e 1000).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Consulta dados cadastrais e classificação setorial."""
    logging.configure_logging(verbose)

    if page < 1:
        typer.echo("✗ Página inválida (deve ser >= 1)", err=True)
        raise typer.Exit(1)

    if page_size < INFO_CAD_PAGE_SIZE_MIN or page_size > INFO_CAD_PAGE_SIZE_MAX:
        typer.echo(
            "✗ Tamanho de página inválido "
            f"(deve estar entre {INFO_CAD_PAGE_SIZE_MIN} e {INFO_CAD_PAGE_SIZE_MAX})",
            err=True,
        )
        raise typer.Exit(1)

    inp = models.InfoCadInput(cnpj=cnpj, verbose=verbose, page=page, page_size=page_size)
    outcome = handlers.info_cad(inp)
    render.render_info_cad_result(outcome)
