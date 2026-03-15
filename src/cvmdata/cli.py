"""CLI principal do cvmdata.

Uso:
    cvmdata download [--year 2024] [--force]
    cvmdata load     [--year 2024]
    cvmdata normalize
    cvmdata indicators [--cnpj 00.000.000/0001-00]
    cvmdata query [--cnpj 00.000.000/0001-00] [--year 2024]
"""
from __future__ import annotations

import logging
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.ingestion.downloader import download_cadastro, download_source_year
from cvmdata.ingestion.loader import load_cadastro, load_source_year
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


@app.command()
def query(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="CNPJ da empresa (ex: 00.000.000/0001-00)."
    ),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Filtrar por ano (ex: 2024)."),
) -> None:
    """Consulta indicadores fundamentalistas calculados."""
    console = Console()

    with get_connection(settings.db_path) as conn:
        try:
            # Sem --cnpj: resumo das 10 empresas com mais indicadores
            if cnpj is None:
                rows = conn.execute(
                    """
                    SELECT cnpj_cia,
                           COUNT(DISTINCT indicador) AS n_indicadores,
                           MIN(dt_refer)             AS primeiro_periodo,
                           MAX(dt_refer)             AS ultimo_periodo
                    FROM   indicators
                    GROUP BY cnpj_cia
                    ORDER BY n_indicadores DESC
                    LIMIT  10
                    """
                ).fetchall()

                if not rows:
                    typer.echo("⚠ Nenhum indicador encontrado — rode 'indicators' primeiro")
                    return

                tbl = Table(title="Top 10 empresas com mais indicadores", show_lines=False)
                tbl.add_column("CNPJ", style="cyan", no_wrap=True)
                tbl.add_column("Indicadores", justify="right")
                tbl.add_column("Primeiro período", justify="center")
                tbl.add_column("Último período", justify="center")
                for row in rows:
                    tbl.add_row(row[0], str(row[1]), str(row[2]), str(row[3]))
                console.print(tbl)
                return

            # Com --cnpj: detalhe por período
            params: list = [cnpj]
            year_clause = ""
            if year is not None:
                year_clause = " AND YEAR(dt_refer) = ?"
                params.append(year)

            rows = conn.execute(
                f"""
                SELECT cnpj_cia, dt_refer, indicador, valor
                FROM   indicators
                WHERE  cnpj_cia = ?{year_clause}
                ORDER BY dt_refer, indicador
                """,
                params,
            ).fetchall()

            if not rows:
                typer.echo(f"⚠ Nenhum indicador encontrado para CNPJ {cnpj!r}")
                return

            tbl = Table(title=f"Indicadores — {cnpj}", show_lines=False)
            tbl.add_column("dt_refer", style="cyan", no_wrap=True)
            tbl.add_column("indicador", style="bold")
            tbl.add_column("valor", justify="right")
            for row in rows:
                valor = f"{row[3]:.4f}" if row[3] is not None else "—"
                tbl.add_row(str(row[1]), row[2], valor)
            console.print(tbl)

        except Exception as exc:
            typer.echo(f"✗ Erro: {exc}", err=True)
            raise typer.Exit(1) from exc


# ── Cadastro CVM ──────────────────────────────────────────────────────────────

@app.command("download-cad")
def download_cad(
    force: bool = typer.Option(False, "--force", "-f", help="Re-baixa mesmo se arquivo já existir."),  # noqa: E501
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Baixa os arquivos cadastrais CVM (meta + CSV) para data/raw/cad/."""
    _setup_logging(verbose)

    settings.cad_dir.mkdir(parents=True, exist_ok=True)
    typer.echo("→ Cadastro CVM")
    try:
        meta_path, csv_path = download_cadastro(
            settings.cad_meta_url,
            settings.cad_csv_url,
            settings.cad_dir,
            force=force,
        )
        typer.echo(f"  ✓ meta: {meta_path.name}")
        typer.echo(f"  ✓ csv:  {csv_path.name} ({csv_path.stat().st_size:,} bytes)")
    except Exception as exc:
        typer.echo(f"  ✗ Erro: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command("load-cad")
def load_cad(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Carrega cad_cia_aberta.csv na tabela cad_cia_aberta_raw do DuckDB."""
    _setup_logging(verbose)

    csv_path = settings.cad_dir / "cad_cia_aberta.csv"
    if not csv_path.exists():
        typer.echo("⚠ Arquivo cadastral não encontrado — rode 'download-cad' primeiro", err=True)
        raise typer.Exit(1)

    typer.echo("→ Carregando cadastro CVM …")
    try:
        with get_connection(settings.db_path) as conn:
            inserted = load_cadastro(conn, csv_path)
        typer.echo(f"  ✓ {inserted:,} linhas em cad_cia_aberta_raw")
    except Exception as exc:
        typer.echo(f"  ✗ Erro: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command("classify-cad")
def classify_cad(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Classifica CNPJs ativos por setor e persiste em company_classification."""
    _setup_logging(verbose)

    from cvmdata.transform.cadastro import classify_cadastro

    typer.echo("→ Classificando cadastro CVM …")
    try:
        with get_connection(settings.db_path) as conn:
            counts = classify_cadastro(conn)
    except RuntimeError as exc:
        typer.echo(f"⚠ {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception as exc:
        typer.echo(f"✗ Erro: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"  ✓ {counts['total']:,} CNPJs classificados "
        f"({counts['high']:,} high, {counts['low']:,} low)"
    )


@app.command("query-cad")
def query_cad(
    cnpj: Optional[str] = typer.Option(
        None, "--cnpj", help="CNPJ da empresa (ex: 12.345.678/0001-99)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Consulta dados cadastrais e classificação setorial."""
    _setup_logging(verbose)
    console = Console()

    with get_connection(settings.db_path) as conn:
        try:
            # Com --cnpj: detalhes de classificação de uma empresa
            if cnpj is not None:
                rows = conn.execute(
                    """
                    SELECT cnpj_cia, cd_cvm, denom_social, denom_comerc,
                           setor_ativ, profile_id, confidence, rule_applied, updated_at
                    FROM   company_classification
                    WHERE  cnpj_cia = ?
                    """,
                    [cnpj],
                ).fetchall()

                if not rows:
                    typer.echo(
                        f"⚠ Nenhuma classificação encontrada para CNPJ {cnpj!r} "
                        "— rode 'classify-cad' primeiro"
                    )
                    raise typer.Exit(1)

                r = rows[0]
                tbl = Table(title=f"Classificação — {cnpj}", show_lines=True)
                for col in ("CNPJ", "CD_CVM", "Razão Social", "Nome Comercial",
                            "Setor Ativ.", "Profile", "Confidence", "Regra", "Atualizado"):
                    tbl.add_column(col, style="cyan" if col == "CNPJ" else None)
                tbl.add_row(*[str(v) if v is not None else "—" for v in r])
                console.print(tbl)
                return

            # Sem --cnpj: resumo das 20 classificações mais recentes
            rows = conn.execute(
                """
                SELECT cnpj_cia, denom_social, setor_ativ, profile_id, confidence, updated_at
                FROM   company_classification
                ORDER BY updated_at DESC
                LIMIT  20
                """
            ).fetchall()

            if not rows:
                typer.echo(
                    "⚠ Nenhuma classificação encontrada — rode 'classify-cad' primeiro"
                )
                raise typer.Exit(1)

            tbl = Table(title="company_classification (últimas 20)", show_lines=False)
            tbl.add_column("CNPJ", style="cyan", no_wrap=True)
            tbl.add_column("Razão Social")
            tbl.add_column("Setor")
            tbl.add_column("Profile", justify="center")
            tbl.add_column("Confidence", justify="center")
            tbl.add_column("Atualizado", justify="center")
            for r in rows:
                tbl.add_row(*[str(v) if v is not None else "—" for v in r])
            console.print(tbl)

        except typer.Exit:
            raise
        except Exception as exc:
            typer.echo(f"✗ Erro: {exc}", err=True)
            raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()
