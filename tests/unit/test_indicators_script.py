"""Testes da busca por empresa do script de indicadores (scripts/indicators.py)."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import duckdb
import pytest
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from indicators import (  # noqa: E402
    render_company_selection_table,
    resolve_companies,
)

from tests.support.builders import setup_classify_schema  # noqa: E402

# denom_comerc vazio é o caso das estrangeiras (Nu, Inter & Co, XP, ...),
# cadastradas no CVM só com razão social.
_EMPRESAS = [
    {
        "CNPJ_CIA": "18.236.120/0001-58",
        "DENOM_SOCIAL": "NU HOLDINGS LTD.",
        "DENOM_COMERC": "",
        "CD_CVM": "369",
    },
    {
        "CNPJ_CIA": "33.045.989/0001-08",
        "DENOM_SOCIAL": "BANCO ITAU S.A.",
        "DENOM_COMERC": "ITAU UNIBANCO",
        "CD_CVM": "325",
    },
    {
        "CNPJ_CIA": "60.641.904/0001-23",
        "DENOM_SOCIAL": "XP INVESTIMENTOS S.A.",
        "DENOM_COMERC": "",
        "CD_CVM": "387",
    },
]


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    setup_classify_schema(con)
    for row in _EMPRESAS:
        con.execute(
            """
            INSERT INTO company_classification
                (cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ,
                 profile_id, rule_applied, updated_at)
            VALUES (?, ?, ?, ?, '', 'default', 'seed', current_timestamp)
            """,
            [row["CNPJ_CIA"], row["CD_CVM"], row["DENOM_SOCIAL"], row["DENOM_COMERC"]],
        )
    return con


def test_search_by_commercial_name(conn: duckdb.DuckDBPyConnection) -> None:
    assert len(resolve_companies(conn, name="itau")) == 1
    assert resolve_companies(conn, name="itau")[0][0] == "33.045.989/0001-08"


def test_search_falls_back_to_legal_name(conn: duckdb.DuckDBPyConnection) -> None:
    """denom_comerc vazio não pode esconder a empresa da busca."""
    assert resolve_companies(conn, name="NU HOLDINGS")[0][0] == "18.236.120/0001-58"
    assert resolve_companies(conn, name="XP INVESTIMENTOS")[0][0] == "60.641.904/0001-23"


def test_search_matches_either_name_and_is_case_insensitive(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # 'BANCO ITAU' é a razão social; 'ITAU UNIBANCO', o nome comercial.
    assert len(resolve_companies(conn, name="itau")) == 1
    assert len(resolve_companies(conn, name="BANCO")) == 1
    assert resolve_companies(conn, name="nao existe") == []


def test_displayed_name_falls_back_to_legal_name(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    cnpj, _cd_cvm, nome, _ticker = resolve_companies(conn, name="NU HOLDINGS")[0]
    assert nome == "NU HOLDINGS LTD."


def test_commercial_name_wins_when_present(conn: duckdb.DuckDBPyConnection) -> None:
    _cnpj, _cd_cvm, nome, _ticker = resolve_companies(conn, name="ITAU UNIBANCO")[0]
    assert nome == "ITAU UNIBANCO"


def test_selection_table_renders_name_column(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    table = render_company_selection_table(resolve_companies(conn, name="NU"), "NU")
    output = io.StringIO()
    Console(file=output, width=100).print(table)
    rendered = output.getvalue()
    assert "NOME" in rendered
    assert "NU HOLDINGS LTD." in rendered