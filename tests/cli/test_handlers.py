"""Testes unitários dos handlers remanescentes do módulo CLI.

A CLI agora expõe apenas consultas (indicadores e info-cad). A execução do
pipeline foi movida para cvmdata.pipeline.
"""

from __future__ import annotations

import duckdb
import pytest

from cvmdata.cli.handlers.ingestion import query
from cvmdata.cli.handlers.transform import query_info_cad
from cvmdata.cli.models import Outcome, QueryInfoCadInput, QueryInput


def test_outcome_factories() -> None:
    ok = Outcome.success(message="ok", payload={"a": 1})
    warn = Outcome.warning(message="warn")
    err = Outcome.error(message="err")

    assert ok.status == "success"
    assert ok.payload == {"a": 1}
    assert warn.status == "warning"
    assert warn.payload is None
    assert err.status == "error"
    assert err.payload is None


# ==========================================================================
# query
# ==========================================================================


def test_query_handler_success_summary(
    monkeypatch: pytest.MonkeyPatch,
    cli_test_db,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_test_db)

    monkeypatch.setattr(query, "get_connection", fake_get_connection)

    outcome = query.handle(QueryInput(cnpj=None, year=None))

    assert outcome.status == "success"
    assert outcome.payload
    assert outcome.payload[0].n_indicadores is not None


def test_query_handler_warning_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    cli_test_db,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_test_db)

    monkeypatch.setattr(query, "get_connection", fake_get_connection)

    outcome = query.handle(QueryInput(cnpj="99.999.999/0001-99", year=2024))

    assert outcome.status == "warning"


def test_query_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    class BrokenConn:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("query failed")

    def fake_get_connection(_):
        return connection_context_factory(BrokenConn())

    monkeypatch.setattr(query, "get_connection", fake_get_connection)

    outcome = query.handle(QueryInput(cnpj=None, year=None))

    assert outcome.status == "error"


# ==========================================================================
# query-info-cad
# ==========================================================================


@pytest.fixture
def cli_info_cad_db() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE company_classification (
            cnpj_cia     VARCHAR,
            cd_cvm       VARCHAR,
            denom_social VARCHAR,
            denom_comerc VARCHAR,
            setor_ativ   VARCHAR,
            profile_id   VARCHAR,
            confidence   VARCHAR,
            rule_applied VARCHAR,
            updated_at   TIMESTAMPTZ
        )
        """
    )
    conn.execute(
        """
        INSERT INTO company_classification
        VALUES
            (
                '00.000.000/0001-91',
                '1234',
                'Banco X',
                'Banco X SA',
                'Bancos',
                'banking',
                'high',
                'setor_ativ:Bancos',
                current_timestamp
            )
        """
    )
    try:
        yield conn
    finally:
        conn.close()


def test_query_info_cad_handler_success_detail(
    monkeypatch: pytest.MonkeyPatch,
    cli_info_cad_db,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_info_cad_db)

    monkeypatch.setattr(query_info_cad, "get_connection", fake_get_connection)

    outcome = query_info_cad.handle(QueryInfoCadInput(cnpj="00.000.000/0001-91", verbose=False))

    assert outcome.status == "success"
    assert outcome.payload
    assert outcome.payload[0].cd_cvm == "1234"


def test_query_info_cad_handler_warning_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    cli_info_cad_db,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_info_cad_db)

    monkeypatch.setattr(query_info_cad, "get_connection", fake_get_connection)

    outcome = query_info_cad.handle(QueryInfoCadInput(cnpj="99.999.999/0001-99", verbose=False))

    assert outcome.status == "warning"


def test_query_info_cad_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    class BrokenConn:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("query failed")

    def fake_get_connection(_):
        return connection_context_factory(BrokenConn())

    monkeypatch.setattr(query_info_cad, "get_connection", fake_get_connection)

    outcome = query_info_cad.handle(QueryInfoCadInput(cnpj=None, verbose=False))

    assert outcome.status == "error"
