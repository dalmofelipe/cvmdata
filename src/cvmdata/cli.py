"""CLI principal do cvmdata.

Uso:
    cvmdata download [--year 2024] [--force]
    cvmdata load     [--year 2024]
    cvmdata normalize
    cvmdata indicators [--cnpj 00.000.000/0001-00]
"""
from __future__ import annotations

import logging
from typing import Optional

import typer

from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.ingestion.downloader import download_source_year
from cvmdata.ingestion.loader import load_source_year
from cvmdata.transform.indicators import calculate_all
from cvmdata.transform.normalize import normalize_all

app = typer.Typer(
    name="cvmdata",
    help="Pipeline de dados CVM para análise fundamentalista.",
    no_args_is_help=True,
)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )


@app.command()
def download(
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Ano específico (ex: 2024)."),
    force: bool = typer.Option(False, "--force", "-f", help="Re-baixa mesmo se ZIP já existir."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Baixa os ZIPs ITR e DFP da CVM para data/raw/."""
    _setup_logging(verbose)
    years = [year] if year else settings.years

    for yr in years:
        for source, url_tmpl in [
            ("itr", settings.itr_url_template),
            ("dfp", settings.dfp_url_template),
        ]:
            typer.echo(f"→ {source.upper()} {yr}")
            try:
                files = download_source_year(
                    source, yr, url_tmpl, settings.raw_dir, force=force
                )
                typer.echo(f"  ✓ {len(files)} CSVs prontos")
            except Exception as exc:
                typer.echo(f"  ✗ Erro: {exc}", err=True)
                raise typer.Exit(1) from exc


@app.command()
def load(
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Ano específico (ex: 2024)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Carrega os CSVs extraídos para o DuckDB (tabelas raw_*)."""
    _setup_logging(verbose)
    years = [year] if year else settings.years

    with get_connection(settings.db_path) as conn:
        for yr in years:
            for source in ("itr", "dfp"):
                typer.echo(f"→ {source.upper()} {yr}")
                try:
                    results = load_source_year(conn, source, yr, settings.raw_dir)
                    if results:
                        total = sum(results.values())
                        typer.echo(f"  ✓ {total:,} linhas em {len(results)} tabelas")
                    else:
                        typer.echo("  ⚠ nenhum arquivo encontrado (rode download primeiro)")
                except Exception as exc:
                    typer.echo(f"  ✗ Erro: {exc}", err=True)
                    raise typer.Exit(1) from exc


@app.command()
def normalize(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Normaliza, deduplica e consolida os dados brutos no DuckDB."""
    _setup_logging(verbose)

    with get_connection(settings.db_path) as conn:
        try:
            results = normalize_all(conn)
        except Exception as exc:
            typer.echo(f"✗ Erro durante normalização: {exc}", err=True)
            raise typer.Exit(1) from exc

    if not results:
        typer.echo("⚠ Nenhuma tabela raw_* encontrada — rode 'load' primeiro")
        return

    for table, count in sorted(results.items()):
        typer.echo(f"  ✓ {table}_clean: {count:,} linhas")

    total = sum(results.values())
    typer.echo(f"✓ {len(results)} tabela(s) normalizadas, {total:,} linhas totais")


@app.command()
def indicators(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="Filtrar por CNPJ (ex: 00.000.000/0001-00)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Calcula indicadores fundamentalistas e grava no DuckDB."""
    _setup_logging(verbose)

    with get_connection(settings.db_path) as conn:
        try:
            total = calculate_all(conn, cnpj=cnpj)
        except Exception as exc:
            typer.echo(f"✗ Erro: {exc}", err=True)
            raise typer.Exit(1) from exc

    if total == 0:
        typer.echo("⚠ Nenhum indicador calculado — rode 'normalize' primeiro")
    else:
        typer.echo(f"✓ {total:,} indicadores gravados em indicators")


if __name__ == "__main__":
    app()
