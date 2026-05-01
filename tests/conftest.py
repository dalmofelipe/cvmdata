"""Fixtures compartilhadas para todos os testes."""

from __future__ import annotations

import duckdb
import pytest


@pytest.fixture
def db():
    """DuckDB in-memory isolado — descartado ao fim de cada teste."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()
