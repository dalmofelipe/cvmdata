# Typer app and command wiring
from __future__ import annotations

from typing import Optional

import typer

from cvmdata.cli import handlers
from cvmdata.cli.logging import configure_logging
from cvmdata.cli.models import (
    DownloadInput,
    IndicatorsInput,
    LoadInput,
    NormalizeInput,
    QueryInput,
)
from cvmdata.cli.render import render_outcome, render_query_result
from cvmdata.config import settings

# ============================================================================
# Typer App Instance (T029)
# ============================================================================

app = typer.Typer(
    name="cvmdata",
    help="Pipeline de dados CVM para análise fundamentalista.",
    no_args_is_help=True,
)


# ============================================================================
# Download Command (T030)
# ============================================================================

@app.command()
def download(
    year: Optional[int] = typer.Option(
        None, "--year", "-y", help="Ano específico (ex: 2024)."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-baixa mesmo se ZIP já existir."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Baixa os ZIPs ITR e DFP da CVM para data/raw/."""
    configure_logging(verbose)
    
    # Validate year if provided
    if year is not None and not (2000 <= year <= 3000):
        typer.echo("✗ Ano inválido (deve estar entre 2000 e 3000)", err=True)
        raise typer.Exit(1)
    
    # Prepare input and delegate to handler
    inp = DownloadInput(
        years=[year] if year else settings.years,
        force=force,
        verbose=verbose,
    )
    outcome = handlers.download.handle(inp)
    render_outcome(outcome)


# ============================================================================
# Load Command (T031)
# ============================================================================

@app.command()
def load(
    year: Optional[int] = typer.Option(
        None, "--year", "-y", help="Ano específico (ex: 2024)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Carrega os CSVs extraídos para o DuckDB (tabelas raw_*)."""
    configure_logging(verbose)
    
    inp = LoadInput(
        years=[year] if year else settings.years,
        verbose=verbose,
    )
    outcome = handlers.load.handle(inp)
    render_outcome(outcome)


# ============================================================================
# Normalize Command (T032)
# ============================================================================

@app.command()
def normalize(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Normaliza, deduplica e consolida os dados brutos no DuckDB."""
    configure_logging(verbose)
    
    inp = NormalizeInput(verbose=verbose)
    outcome = handlers.normalize.handle(inp)
    render_outcome(outcome)


# ============================================================================
# Indicators Command (T033)
# ============================================================================

@app.command()
def indicators(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="Filtrar por CNPJ (ex: 00.000.000/0001-00)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Calcula indicadores fundamentalistas e grava no DuckDB."""
    configure_logging(verbose)
    
    inp = IndicatorsInput(cnpj=cnpj, verbose=verbose)
    outcome = handlers.indicators.handle(inp)
    render_outcome(outcome)


# ============================================================================
# Query Command (T034)
# ============================================================================

@app.command()
def query(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="CNPJ da empresa (ex: 00.000.000/0001-00)."
    ),
    year: Optional[int] = typer.Option(
        None, "--year", "-y", help="Filtrar por ano (ex: 2024)."
    ),
) -> None:
    """Consulta indicadores fundamentalistas calculados."""
    if year is not None and not (2000 <= year <= 3000):
        typer.echo("✗ Ano inválido (deve estar entre 2000 e 3000)", err=True)
        raise typer.Exit(1)

    inp = QueryInput(cnpj=cnpj, year=year)
    outcome = handlers.query.handle(inp)
    render_query_result(outcome)

