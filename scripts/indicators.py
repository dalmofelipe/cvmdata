"""Consulta os indicadores fundamentalistas já calculados para uma empresa.

Camada de leitura pura: não recalcula nada, só consulta a tabela `indicators`
(produzida por `transform.indicators.calculate_all`) e apresenta o resultado.

Uso:
    indicators [--cnpj CNPJ | --ticker TICKER | --cod_cvm COD | --name NOME]
               [--year ANO]

    uv run python -m cvmdata.scripts.indicators
    uv run python -m cvmdata.scripts.indicators --ticker PETR
    uv run python -m cvmdata.scripts.indicators --cnpj "33.000.167/0001-01" --year 2024
    uv run python -m cvmdata.scripts.indicators --name "BRASIL"
"""

from __future__ import annotations

import argparse
import logging

import duckdb
from rich.console import Console
from rich.table import Table

from cvmdata.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CNPJ = "33.000.167/0001-01"  # Petrobras
NAME_MIN_LENGTH = 4  # mínimo de caracteres para --name


def _b3_tickers_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    result = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'b3_tickers'"
    ).fetchone()
    return result[0] > 0


def resolve_companies(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
    ticker: str | None = None,
    cod_cvm: str | None = None,
    name: str | None = None,
) -> list[tuple[str, str, str, str | None]]:
    """Resolve filtros de empresa para uma lista de (cnpj, cd_cvm, denom_comerc, ticker).

    Retorna tuplas na ordem:
        (cnpj_cia, cd_cvm, denom_comerc, ticker_root)

    O campo ticker_root é None quando a tabela b3_tickers não existe ou
    quando não há correspondência no LEFT JOIN.
    """
    has_ticker_filter = ticker is not None
    b3_exists = _b3_tickers_exists(conn)

    if has_ticker_filter and not b3_exists:
        logger.warning("tabela b3_tickers não existe — impossível filtrar por --ticker")
        return []

    conditions: list[str] = []
    params: list[str] = []

    select_cols = "cc.cnpj_cia, cc.cd_cvm, cc.denom_comerc"
    from_clause = "FROM company_classification cc"

    if b3_exists:
        select_cols += ", bt.ticker_root"
        from_clause += " LEFT JOIN b3_tickers bt ON CAST(cc.cd_cvm AS INTEGER) = bt.cod_cvm"
    else:
        select_cols += ", NULL AS ticker_root"

    if cnpj is not None:
        conditions.append("cc.cnpj_cia = ?")
        params.append(cnpj)

    if cod_cvm is not None:
        conditions.append("cc.cd_cvm = ?")
        params.append(cod_cvm)

    if name is not None:
        conditions.append("UPPER(cc.denom_comerc) LIKE ?")
        params.append(f"%{name.upper()}%")

    if ticker is not None:
        conditions.append("UPPER(bt.ticker_root) = UPPER(?)")
        params.append(ticker)

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"SELECT {select_cols} {from_clause} WHERE {where_clause}"

    return conn.execute(query, params).fetchall()


def fetch_indicators(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str,
    year: int | None = None,
) -> list[tuple[str, str, float | None]]:
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


def render_company_selection_table(
    companies: list[tuple[str, str, str, str | None]],
    search_term: str,
) -> Table:
    table = Table(title=f"Empresas encontradas para '{search_term}'")
    table.add_column("CNPJ")
    table.add_column("COD_CVM")
    table.add_column("TICKER")
    table.add_column("DENOM_COMERCIAL")

    for cnpj, cd_cvm, denom_comerc, ticker_root in companies:
        ticker_str = ticker_root if ticker_root else "—"
        table.add_row(cnpj, cd_cvm, ticker_str, denom_comerc)

    return table


def render_indicators_table(
    cnpj: str,
    denom_comerc: str,
    ticker_root: str | None,
    rows: list[tuple[str, str, float | None]],
) -> Table:
    title = f"Indicadores — {cnpj} — {denom_comerc}"
    if ticker_root:
        title += f" ({ticker_root})"
    table = Table(title=title)
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
        default=None,
        help="CNPJ da empresa, formato mascarado (ex: 33.000.167/0001-01).",
    )
    parser.add_argument(
        "--ticker",
        default=None,
        help="Ticker da ação (4 letras, ex: PETR).",
    )
    parser.add_argument(
        "--cod_cvm",
        default=None,
        help="Código CVM da empresa.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help=f"Denominação comercial da empresa (mínimo {NAME_MIN_LENGTH} caracteres).",
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

    # ── validações ──────────────────────────────────────────────────────────

    if args.name:
        args.name = args.name.strip()
        if len(args.name) < NAME_MIN_LENGTH:
            console.print(f"[red]--name deve ter no mínimo {NAME_MIN_LENGTH} caracteres[/red]")
            raise SystemExit(1)

    if args.ticker:
        args.ticker = args.ticker.strip().upper()
        if not args.ticker.isalpha() or len(args.ticker) != 4:
            console.print(
                "[red]--ticker deve conter exatamente 4 letras (ex: PETR)[/red]"
            )
            raise SystemExit(1)

    # ── fallback para Petrobras quando nenhum filtro de empresa é informado ─

    has_company_filter = any([args.cnpj, args.ticker, args.cod_cvm, args.name])
    if not has_company_filter:
        args.cnpj = DEFAULT_CNPJ

    # ── resolução da empresa ────────────────────────────────────────────────

    try:
        with duckdb.connect(str(settings.db_path), read_only=True) as conn:
            companies = resolve_companies(
                conn,
                cnpj=args.cnpj,
                ticker=args.ticker,
                cod_cvm=args.cod_cvm,
                name=args.name,
            )
    except duckdb.IOException as e:
        console.print(f"[red]Erro ao abrir o banco: {e}[/red]")
        raise SystemExit(1)

    if not companies:
        console.print("[yellow]Nenhuma empresa encontrada com os filtros informados.[/yellow]")
        raise SystemExit(1)

    if len(companies) > 1:
        console.print(render_company_selection_table(companies, args.name or ""))
        return

    # ── indicadores ─────────────────────────────────────────────────────────

    cnpj, _, denom_comerc, ticker_root = companies[0]

    try:
        with duckdb.connect(str(settings.db_path), read_only=True) as conn:
            rows = fetch_indicators(conn, cnpj, args.year)
    except duckdb.IOException as e:
        console.print(f"[red]Erro ao abrir o banco: {e}[/red]")
        raise SystemExit(1)

    if not rows:
        filtro_ano = f" ano={args.year}" if args.year is not None else ""
        console.print(f"[yellow]Nenhum indicador encontrado para {cnpj}{filtro_ano}.[/yellow]")
        raise SystemExit(1)

    console.print(render_indicators_table(cnpj, denom_comerc, ticker_root, rows))


if __name__ == "__main__":
    main()
