from __future__ import annotations

import duckdb
import pytest

from cvmdata.ingestion.schema import init_indicators_schema
from cvmdata.transform.indicators.calculate_all import _persist_rows
from cvmdata.transform.indicators.models import IndicatorRow

pytestmark = pytest.mark.unit


def test_persist_rows_rolls_back_when_insert_fails():
    conn = duckdb.connect(":memory:")
    try:
        init_indicators_schema(conn)
        conn.execute(
            "INSERT INTO indicators VALUES ('company', '2024-01-01', 'roe', 10.0)"
        )

        with pytest.raises(duckdb.Error):
            _persist_rows(
                conn,
                None,
                [IndicatorRow("company", "not-a-date", "roe", 20.0)],
            )

        assert conn.execute("SELECT valor FROM indicators").fetchall() == [(10.0,)]
    finally:
        conn.close()
