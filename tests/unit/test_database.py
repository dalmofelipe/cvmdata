from __future__ import annotations

import duckdb
import pytest

from cvmdata.ingestion.database import get_connection
from cvmdata.utils.database import (
    DuckDBValidationError,
    replace_table_contents,
    sanitize_duckdb_memory_limit,
    sanitize_duckdb_threads,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("2gb", "2GB"), ("500MB", "500MB"), ("80%", "80%")],
)
def test_sanitize_memory_limit(value, expected):
    assert sanitize_duckdb_memory_limit(value) == expected


def test_sanitize_memory_limit_rejects_zero():
    with pytest.raises(DuckDBValidationError):
        sanitize_duckdb_memory_limit("0GB")


@pytest.mark.parametrize("value", [0, -1])
def test_sanitize_threads_rejects_non_positive_values(value):
    with pytest.raises(DuckDBValidationError):
        sanitize_duckdb_threads(value)


def test_sanitize_threads_accepts_positive_value():
    assert sanitize_duckdb_threads(2) == 2


def test_get_connection_applies_threads_and_memory_limit(tmp_path):
    conn = get_connection(
        db_path=tmp_path / "db.duckdb",
        memory_limit="128MB",
        threads=2,
    )
    try:
        assert conn.execute("SELECT current_setting('threads')").fetchone()[0] == 2
        assert conn.execute("SELECT current_setting('memory_limit')").fetchone()[0] == "122.0 MiB"
    finally:
        conn.close()


def test_replace_table_contents_rolls_back_on_insert_failure():
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("CREATE TABLE target (value INTEGER)")
        conn.execute("INSERT INTO target VALUES (7)")

        with pytest.raises(duckdb.Error):
            replace_table_contents(
                conn,
                "target",
                "INSERT INTO target VALUES (?)",
                ["not an integer"],
            )

        assert conn.execute("SELECT * FROM target").fetchall() == [(7,)]
    finally:
        conn.close()
