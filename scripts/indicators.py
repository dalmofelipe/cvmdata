"""Consulta os indicadores fundamentalistas já calculados para uma empresa.

Camada de leitura pura: não recalcula nada, só consulta a tabela `indicators`
(produzida por `transform.indicators.calculate_all`) e apresenta o resultado.

Uso:
    indicators --cnpj <CNPJ> [--year <ANO>]
    
    uv run python -m cvmdata.scripts.indicators
    uv run python -m cvmdata.scripts.indicators --cnpj "33.000.167/0001-01"
    uv run python -m cvmdata.scripts.indicators --cnpj "33.000.167/0001-01" --year 2024
"""

from __future__ import annotations

import argparse
import logging

import duckdb
from rich.console import Console
from rich.table import Table

from cvmdata.config import settings

logger = logging.getLogger(__name__)

# CNPJ usado como padrão quando o script é executado sem argumentos.
DEFAULT_CNPJ = "33.000.167/0001-01"  # Petrobras


def fetch_indicators(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str,
    year: int | None = None,
) -> list[tuple[str, str, float | None]]:
    """Consulta a tabela `indicators` para um CNPJ, opcionalmente filtrado por ano.

    Args:
        conn: Conexão DuckDB já aberta, com a tabela `indicators` populada.
        cnpj: CNPJ da empresa no formato mascarado (ex: "33.000.167/0001-01"),
            igual ao que é gravado em `cnpj_cia` durante o load dos CSVs da CVM.
        year: Se fornecido, filtra apenas os registros cujo `dt_refer` cai
            nesse ano (ex: 2024). Se None, retorna todos os anos disponíveis.

    Returns:
        Lista de tuplas (dt_refer, indicador, valor), ordenada por data e
        depois por nome do indicador. `valor` pode ser None quando o cálculo
        não teve dados suficientes para aquele período.
    """
    query = """
        SELECT dt_refer::VARCHAR, indicador, valor
        FROM indicators
        WHERE cnpj_cia = ?
    """
    params: list[str | int] = [cnpj]

    if year is not None:
        query += " AND EXTRACT(YEAR FROM dt_refer) = ?"
        params.append(year)

    query += " ORDER BY dt_refer, indicador"

    return conn.execute(query, params).fetchall()


def fetch_denom_comerc(conn: duckdb.DuckDBPyConnection, cnpj: str) -> str:
    query = """
        SELECT denom_comerc
        FROM company_classification
        WHERE cnpj_cia = ?
    """
    result = conn.execute(query, [cnpj]).fetchone()
    return result[0] if result else "Desconhecido"


def render_table(
    cnpj: str, 
    denom_comerc: str,
    rows: list[tuple[str, str, float | None]]
) -> Table:
    table = Table(title=f"Indicadores — {cnpj} - {denom_comerc}")
    table.add_column("dt_refer")
    table.add_column("indicador")
    table.add_column("valor", justify="right")

    for dt_refer, indicador, valor in rows:
        valor_str = f"{valor:.4f}" if valor is not None else "—"
        table.add_row(dt_refer, indicador, valor_str)

    return table


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consulta os indicadores fundamentalistas calculados para uma empresa.",
    )
    parser.add_argument(
        "--cnpj",
        default=DEFAULT_CNPJ,
        help=f"CNPJ da empresa, formato mascarado (padrão: {DEFAULT_CNPJ} — Petrobras).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Filtra por ano de dt_refer (ex: 2024). Padrão: todos os anos disponíveis.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    console = Console()

    if not settings.db_path.exists():
        console.print(
            f"[red]Banco não encontrado em {settings.db_path} — "
            "rode o pipeline principal (`uv run cvmdata`) antes de consultar.[/red]"
        )
        raise SystemExit(1)

    try:
        with duckdb.connect(str(settings.db_path), read_only=True) as conn:
            rows = fetch_indicators(conn, args.cnpj, args.year)
            denom_comerc = fetch_denom_comerc(conn, args.cnpj)
    except duckdb.IOException as e:
        console.print(f"[red]Erro ao abrir o banco: {e}[/red]")
        raise SystemExit(1)
    
    if not rows:
        filtro_ano = f" ano={args.year}" if args.year is not None else ""
        console.print(
            f"[yellow]Nenhum indicador encontrado para cnpj={args.cnpj}{filtro_ano}.[/yellow]"
        )
        raise SystemExit(1)

    console.print(render_table(args.cnpj, denom_comerc, rows))


if __name__ == "__main__":
    main()
