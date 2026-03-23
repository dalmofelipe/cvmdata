# Output rendering and exit code mapping
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from cvmdata.cli.models import Outcome, QueryResult


# ============================================================================
# Main Rendering Function (T013)
# ============================================================================

def render_outcome(outcome: Outcome[Any]) -> None:
    """Render outcome message and set process exit code.
    
    Maps outcome status to user-facing output and exit code:
    - success: ✓ prefix, stdout, exit 0
    - warning: ⚠ prefix, stdout, exit 0 (benign, not failure)
    - error: ✗ prefix, stderr, exit 1
    
    Args:
        outcome: Outcome object from handler.
    
    Raises:
        typer.Exit: Always (with code 0 or 1 based on status).
    """
    if outcome.status == "success":
        if outcome.message:
            typer.echo(f"✓ {outcome.message}")
        raise typer.Exit(0)
    
    elif outcome.status == "warning":
        if outcome.message:
            typer.echo(f"⚠ {outcome.message}", err=False)
        raise typer.Exit(0)
    
    elif outcome.status == "error":
        if outcome.message:
            typer.echo(f"✗ {outcome.message}", err=True)
        raise typer.Exit(1)


# ============================================================================
# Query-Specific Rendering (Rich Table)
# ============================================================================

def render_query_result(outcome: Outcome[list[QueryResult]]) -> None:
    """Render query command outcome with rich.Table for summary or detail.
    
    Detects query type (summary vs detail) by checking for n_indicadores field.
    
    Args:
        outcome: Outcome from query handler with list[QueryResult] payload.
    
    Raises:
        typer.Exit: Always (with code 0 or 1 based on status).
    """
    console = Console()
    
    if outcome.status == "warning" or not outcome.payload:
        if outcome.message:
            typer.echo(f"⚠ {outcome.message}", err=False)
        raise typer.Exit(0)
    
    if outcome.status == "error":
        if outcome.message:
            typer.echo(f"✗ {outcome.message}", err=True)
        raise typer.Exit(1)
    
    results = outcome.payload
    
    # Detect query type: summary (n_indicadores set) vs detail
    if results and results[0].n_indicadores is not None:
        # Summary: top companies with most indicators
        tbl = Table(title="Top companies with most indicators", show_lines=False)
        tbl.add_column("CNPJ", style="cyan", no_wrap=True)
        tbl.add_column("Indicators", justify="right")
        tbl.add_column("First period", justify="center")
        tbl.add_column("Last period", justify="center")
        for row in results:
            tbl.add_row(
                row.cnpj_cia,
                str(row.n_indicadores),
                str(row.primeiro_periodo),
                str(row.ultimo_periodo),
            )
    else:
        # Detail: indicators by period for specific company
        cnpj_display = results[0].cnpj_cia if results else "unknown"
        tbl = Table(title=f"Indicators — {cnpj_display}", show_lines=False)
        tbl.add_column("Period", style="cyan", no_wrap=True)
        tbl.add_column("Indicator")
        tbl.add_column("Value", justify="right")
        for row in results:
            valor_str = f"{row.valor:.4f}" if row.valor is not None else "—"
            tbl.add_row(str(row.dt_refer), str(row.indicador), valor_str)
    
    console.print(tbl)
    raise typer.Exit(0)

