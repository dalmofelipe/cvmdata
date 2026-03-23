"""Fixtures de suporte para testes do módulo CLI."""

from __future__ import annotations

import duckdb
import pytest


@pytest.fixture
def cli_test_db() -> duckdb.DuckDBPyConnection:
    """Cria um DuckDB em memória com tabela `indicators` e dados mínimos."""
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE indicators (
            cnpj_cia  VARCHAR,
            dt_refer  DATE,
            indicador VARCHAR,
            valor     DOUBLE
        )
        """
    )
    conn.execute(
        """
        INSERT INTO indicators (cnpj_cia, dt_refer, indicador, valor)
        VALUES
            ('00.000.000/0001-91', DATE '2024-12-31', 'ROE', 0.1234),
            ('00.000.000/0001-91', DATE '2024-12-31', 'ROA', 0.0678),
            ('11.111.111/0001-11', DATE '2023-12-31', 'ROE', 0.2000)
        """
    )
    try:
        yield conn
    finally:
        conn.close()


class _ConnectionContext:
    """Context manager simples para injetar conexão fake nos handlers."""

    def __init__(self, conn: object) -> None:
        self._conn = conn

    def __enter__(self) -> object:
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.fixture
def connection_context_factory():
    """Fábrica de context manager para monkeypatch de get_connection."""

    def _factory(conn: object) -> _ConnectionContext:
        return _ConnectionContext(conn)

    return _factory
