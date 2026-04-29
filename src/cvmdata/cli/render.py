# Output rendering and exit code mapping
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from cvmdata.cli.models import Outcome, QueryInfoCadResult, QueryResult


def _format_confidence(value: float | str | None) -> str:
    """Normaliza exibição de confidence sem assumir tipo numérico.

    company_classification.confidence pode vir como texto (ex.: "high")
    ou número (ex.: 0.95), dependendo da origem dos dados.
    """
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    # Keep non-numeric labels as-is (e.g., "high", "low")
    return str(value)


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
    """Renderiza saída do comando query em tabela Rich."""
    console = Console()

    if outcome.status == "error":
        if outcome.message:
            typer.echo(f"✗ {outcome.message}", err=True)
        raise typer.Exit(1)

    if outcome.status == "warning" or not outcome.payload:
        if outcome.message:
            typer.echo(f"⚠ {outcome.message}", err=False)
        raise typer.Exit(0)

    results = outcome.payload

    # Detect query type: summary (n_indicadores set) vs detail
    if results and results[0].n_indicadores is not None:
        # Summary: top companies with most indicators
        tbl = Table(title="Top 10 empresas com mais indicadores", show_lines=False)
        tbl.add_column("CNPJ", style="cyan", no_wrap=True)
        tbl.add_column("Indicadores", justify="right")
        tbl.add_column("Primeiro período", justify="center")
        tbl.add_column("Último período", justify="center")
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
        tbl = Table(title=f"Indicadores — {cnpj_display}", show_lines=False)
        tbl.add_column("dt_refer", style="cyan", no_wrap=True)
        tbl.add_column("indicador")
        tbl.add_column("valor", justify="right")
        for row in results:
            valor_str = f"{row.valor:.4f}" if row.valor is not None else "—"
            tbl.add_row(str(row.dt_refer), str(row.indicador), valor_str)

    console.print(tbl)
    raise typer.Exit(0)


# ============================================================================
# Query Informações Cadastrais Rendering (Rich Table, 2 modes: summary vs detail)
# ============================================================================


def render_query_info_cad_result(outcome: Outcome[list[QueryInfoCadResult]]) -> None:
    """Renderiza saída do comando query-cad com suporte a dois modos.

    Summary mode (no --cnpj):
    - Últimas 20 classificações com CNPJ, Razão Social, Setor, Profile, Confidence, Atualizado

    Detail mode (com --cnpj):
    - Detalhe completo com todas as colunas de company_classification
    """
    console = Console()

    if outcome.status == "error":
        if outcome.message:
            typer.echo(f"✗ {outcome.message}", err=True)
        raise typer.Exit(1)

    if outcome.status == "warning" or not outcome.payload:
        if outcome.message:
            typer.echo(f"⚠ {outcome.message}", err=False)
        raise typer.Exit(0)

    results = outcome.payload

    # Detect mode: detail if cd_cvm is populated
    if results and results[0].cd_cvm is not None:
        # Detail mode: full record for specific CNPJ
        cnpj_display = results[0].cnpj_cia if results else "unknown"
        tbl = Table(title=f"Classificação — {cnpj_display}", show_lines=True)
        tbl.add_column("CNPJ", style="cyan")
        tbl.add_column("CD_CVM")
        tbl.add_column("Razão Social")
        tbl.add_column("Nome Comercial")
        tbl.add_column("Setor Ativ.")
        tbl.add_column("Profile")
        tbl.add_column("Confidence", justify="center")
        tbl.add_column("Regra")
        tbl.add_column("Atualizado", justify="center")

        for row in results:
            tbl.add_row(
                row.cnpj_cia,
                row.cd_cvm or "—",
                row.denom_social or "—",
                row.denom_comerc or "—",
                row.setor_ativ or "—",
                row.profile_id or "—",
                _format_confidence(row.confidence),
                row.rule_applied or "—",
                row.updated_at or "—",
            )
    else:
        # Summary mode: last 20 classifications
        tbl = Table(title="company_classification (últimas 20)", show_lines=False)
        tbl.add_column("CNPJ", style="cyan", no_wrap=True)
        tbl.add_column("Razão Social")
        tbl.add_column("Setor")
        tbl.add_column("Profile", justify="center")
        tbl.add_column("Confidence", justify="center")
        tbl.add_column("Atualizado", justify="center")

        for row in results:
            tbl.add_row(
                row.cnpj_cia,
                row.denom_social or "—",
                row.setor_ativ or "—",
                row.profile_id or "—",
                _format_confidence(row.confidence),
                row.updated_at or "—",
            )

    console.print(tbl)
    raise typer.Exit(0)
