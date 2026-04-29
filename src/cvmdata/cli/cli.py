"""Typer CLI wiring.

A CLI expõe apenas comandos de consulta e um único comando de orquestração do
pipeline completo.
"""

from __future__ import annotations

from typing import Optional

import typer

from cvmdata.cli import handlers
from cvmdata.cli.logging import configure_logging
from cvmdata.cli.models import QueryInfoCadInput, QueryInput
from cvmdata.cli.render import render_query_info_cad_result, render_query_result
from cvmdata.config import settings
from cvmdata.pipeline import PipelineExecutionError, YearsParseError, parse_years, run_full
from cvmdata.pipeline.models import PipelineReport

app = typer.Typer(
    name="cvmdata",
    no_args_is_help=True,
)


pipeline_app = typer.Typer(
    help="Executa o pipeline completo (financeiro + cadastral).",
    no_args_is_help=True,
)

app.add_typer(pipeline_app, name="pipeline")


def _render_pipeline_report(report: PipelineReport) -> None:
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
    configure_logging(verbose)

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
# Query Command (T034)
# ============================================================================


@app.command()
def query(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="CNPJ da empresa (ex: 00.000.000/0001-00)."
    ),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Filtrar por ano (ex: 2024)."),
) -> None:
    """Consulta indicadores fundamentalistas calculados."""
    if year is not None and not (2000 <= year <= 3000):
        typer.echo("✗ Ano inválido (deve estar entre 2000 e 3000)", err=True)
        raise typer.Exit(1)

    inp = QueryInput(cnpj=cnpj, year=year)
    outcome = handlers.query.handle(inp)
    render_query_result(outcome)


# ============================================================================
@app.command("query-info-cad")
def query_info_cad(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="CNPJ da empresa (ex: 12.345.678/0001-99)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Consulta dados cadastrais e classificação setorial."""
    configure_logging(verbose)

    inp = QueryInfoCadInput(cnpj=cnpj, verbose=verbose)
    outcome = handlers.query_info_cad.handle(inp)
    render_query_info_cad_result(outcome)
