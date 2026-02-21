#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["duckdb>=1.2", "rich>=13"]
# ///
"""Lista as empresas presentes no banco de dados cvmdata.

Uso:
    uv run scripts/list_companies.py
    uv run scripts/list_companies.py --limit 50
    uv run scripts/list_companies.py --filter petro
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
from rich.console import Console
from rich.table import Table

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "cvmdata.duckdb"

# args simples sem typer
limit = 20
name_filter = ""
for i, arg in enumerate(sys.argv[1:]):
    if arg == "--limit" and i + 1 < len(sys.argv) - 1:
        limit = int(sys.argv[i + 2])
    elif arg == "--filter" and i + 1 < len(sys.argv) - 1:
        name_filter = sys.argv[i + 2]

if not DB_PATH.exists():
    print(f"✗ Banco não encontrado: {DB_PATH}")
    sys.exit(1)

conn = duckdb.connect(str(DB_PATH), read_only=True)

# Verifica tabelas disponíveis
available = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}

if "indicators" in available:
    filter_clause = f"AND LOWER(denom_cia) LIKE '%{name_filter.lower()}%'" if name_filter else ""
    sql = f"""
        SELECT
            i.cnpj_cia,
            b.denom_cia,
            COUNT(DISTINCT i.indicador)            AS n_indicadores,
            COUNT(DISTINCT i.dt_refer)             AS n_periodos,
            MIN(i.dt_refer)                        AS primeiro,
            MAX(i.dt_refer)                        AS ultimo
        FROM indicators i
        LEFT JOIN (
            SELECT DISTINCT cnpj_cia, denom_cia
            FROM raw_bpa
        ) b ON b.cnpj_cia = i.cnpj_cia
        WHERE 1=1 {filter_clause}
        GROUP BY i.cnpj_cia, b.denom_cia
        ORDER BY n_periodos DESC, n_indicadores DESC
        LIMIT {limit}
    """
elif "raw_bpa" in available:
    filter_clause = f"AND LOWER(denom_cia) LIKE '%{name_filter.lower()}%'" if name_filter else ""
    sql = f"""
        SELECT
            cnpj_cia,
            denom_cia,
            COUNT(DISTINCT dt_refer) AS periodos,
            MIN(dt_refer)            AS primeiro,
            MAX(dt_refer)            AS ultimo
        FROM raw_bpa
        WHERE 1=1 {filter_clause}
        GROUP BY cnpj_cia, denom_cia
        ORDER BY periodos DESC
        LIMIT {limit}
    """
else:
    print("⚠ Nenhuma tabela encontrada — rode 'cvmdata load' primeiro.")
    sys.exit(0)

rows = conn.execute(sql).fetchall()
conn.close()

if not rows:
    print("⚠ Nenhuma empresa encontrada.")
    sys.exit(0)

console = Console()
title = f"Empresas no banco{' (filtro: ' + name_filter + ')' if name_filter else ''}"

if "indicators" in available:
    tbl = Table(title=title, show_lines=False)
    tbl.add_column("CNPJ", style="cyan", no_wrap=True)
    tbl.add_column("Nome", style="bold", max_width=40)
    tbl.add_column("Indicadores", justify="right")
    tbl.add_column("Períodos", justify="right")
    tbl.add_column("Primeiro", justify="center")
    tbl.add_column("Último", justify="center")
    for r in rows:
        tbl.add_row(r[0], r[1] or "—", str(r[2]), str(r[3]), str(r[4]), str(r[5]))
else:
    tbl = Table(title=title, show_lines=False)
    tbl.add_column("CNPJ", style="cyan", no_wrap=True)
    tbl.add_column("Nome", style="bold", max_width=40)
    tbl.add_column("Períodos", justify="right")
    tbl.add_column("Primeiro", justify="center")
    tbl.add_column("Último", justify="center")
    for r in rows:
        tbl.add_row(r[0], r[1] or "—", str(r[2]), str(r[3]), str(r[4]))

console.print(tbl)
console.print(f"[dim]{len(rows)} empresa(s) exibidas (--limit {limit})[/dim]")
