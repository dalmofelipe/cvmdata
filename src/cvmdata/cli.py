"""CLI principal do cvmdata.

Uso:
    cvmdata download [--year 2024]
    cvmdata load     [--year 2024]
    cvmdata normalize
    cvmdata indicators [--cnpj 00.000.000/0001-00]
"""
from __future__ import annotations

from typing import Optional

import typer

from cvmdata.config import settings  # noqa: F401

app = typer.Typer(
    name="cvmdata",
    help="Pipeline de dados CVM para análise fundamentalista.",
    no_args_is_help=True,
)


@app.command()
def download(
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Ano específico (ex: 2024)."),
) -> None:
    """Baixa os ZIPs ITR e DFP da CVM para data/raw/."""
    years = [year] if year else settings.years
    typer.echo(f"[download] anos={years}  — não implementado ainda")


@app.command()
def load(
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Ano específico (ex: 2024)."),
) -> None:
    """Carrega os CSVs extraídos para o DuckDB (tabela raw_*)."""
    years = [year] if year else settings.years
    typer.echo(f"[load] anos={years}  — não implementado ainda")


@app.command()
def normalize() -> None:
    """Normaliza, deduplica e consolida os dados brutos no DuckDB."""
    typer.echo("[normalize]  — não implementado ainda")


@app.command()
def indicators(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="Filtrar por CNPJ (ex: 00.000.000/0001-00)."
    ),
) -> None:
    """Calcula indicadores fundamentalistas e grava no DuckDB."""
    typer.echo(f"[indicators] cnpj={cnpj}  — não implementado ainda")


if __name__ == "__main__":
    app()
