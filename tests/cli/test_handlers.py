"""Testes unitários dos handlers remanescentes do módulo CLI.

A CLI agora expõe apenas consultas (indicadores e info-cad). A execução do
pipeline foi movida para cvmdata.pipeline.
"""

from __future__ import annotations

import duckdb
import pytest

from cvmdata.cli import handlers
from cvmdata.cli.models import IndicatorsInput, InfoCadInput, Outcome, Paged


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
# indicators (handler `query`)
# ==========================================================================


def test_indicators_handler_success_detail(
    monkeypatch: pytest.MonkeyPatch,
    cli_test_db,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_test_db)

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.indicators(IndicatorsInput(cnpj="00.000.000/0001-91", year=None))

    assert outcome.status == "success"
    assert outcome.payload
    assert outcome.payload[0].indicador is not None


def test_indicators_handler_warning_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    cli_test_db,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_test_db)

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.indicators(IndicatorsInput(cnpj="99.999.999/0001-99", year=2024))

    assert outcome.status == "warning"


def test_indicators_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    class BrokenConn:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("query failed")

    def fake_get_connection(_):
        return connection_context_factory(BrokenConn())

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.indicators(IndicatorsInput(cnpj="00.000.000/0001-91", year=None))

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


@pytest.fixture
def cli_info_cad_db_many() -> duckdb.DuckDBPyConnection:
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

    # Insert 25 rows with same updated_at to validate stable ordering by cnpj_cia
    for i in range(1, 26):
        cnpj = f"00.000.000/0001-{i:02d}"
        conn.execute(
            """
            INSERT INTO company_classification(
                cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ, profile_id, 
                confidence, rule_applied, updated_at
            )
            VALUES (
                ?, NULL, ?, NULL, 'Setor', 'profile', 'high', NULL, TIMESTAMPTZ 
                '2024-01-01 00:00:00+00'
            )
            """,
            [cnpj, f"Empresa {i:02d}"],
        )

    try:
        yield conn
    finally:
        conn.close()


def test_info_cad_handler_success_detail(
    monkeypatch: pytest.MonkeyPatch,
    cli_info_cad_db,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_info_cad_db)

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.info_cad(InfoCadInput(cnpj="00.000.000/0001-91", verbose=False))

    assert outcome.status == "success"
    assert outcome.payload
    assert outcome.payload[0].cd_cvm == "1234"


def test_info_cad_handler_warning_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    cli_info_cad_db,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_info_cad_db)

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.info_cad(InfoCadInput(cnpj="99.999.999/0001-99", verbose=False))

    assert outcome.status == "warning"


def test_info_cad_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    class BrokenConn:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("query failed")

    def fake_get_connection(_):
        return connection_context_factory(BrokenConn())

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.info_cad(InfoCadInput(cnpj=None, verbose=False))

    assert outcome.status == "error"


def test_info_cad_handler_summary_pagination_page_1(
    monkeypatch: pytest.MonkeyPatch,
    cli_info_cad_db_many,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_info_cad_db_many)

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.info_cad(InfoCadInput(cnpj=None, verbose=False, page=1))

    assert outcome.status == "success"
    assert outcome.payload
    assert isinstance(outcome.payload, Paged)
    assert outcome.payload.page == 1
    assert outcome.payload.page_size == 20
    assert len(outcome.payload.items) == 20
    assert outcome.payload.items[0].cnpj_cia.endswith("-01")
    assert outcome.payload.items[-1].cnpj_cia.endswith("-20")


def test_info_cad_handler_summary_pagination_page_2(
    monkeypatch: pytest.MonkeyPatch,
    cli_info_cad_db_many,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_info_cad_db_many)

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.info_cad(InfoCadInput(cnpj=None, verbose=False, page=2))

    assert outcome.status == "success"
    assert outcome.payload
    assert isinstance(outcome.payload, Paged)
    assert outcome.payload.page == 2
    assert outcome.payload.page_size == 20
    assert len(outcome.payload.items) == 5
    assert outcome.payload.items[0].cnpj_cia.endswith("-21")
    assert outcome.payload.items[-1].cnpj_cia.endswith("-25")


def test_info_cad_handler_summary_uses_custom_page_size(
    monkeypatch: pytest.MonkeyPatch,
    cli_info_cad_db_many,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_info_cad_db_many)

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.info_cad(InfoCadInput(cnpj=None, verbose=False, page=1, page_size=50))

    assert outcome.status == "success"
    assert isinstance(outcome.payload, Paged)
    assert outcome.payload.page_size == 50
    assert len(outcome.payload.items) == 25


def test_info_cad_handler_rejects_page_size_below_minimum(
    monkeypatch: pytest.MonkeyPatch,
    cli_info_cad_db_many,
    connection_context_factory,
) -> None:
    def fake_get_connection(_):
        return connection_context_factory(cli_info_cad_db_many)

    monkeypatch.setattr(handlers.db, "get_connection", fake_get_connection)

    outcome = handlers.info_cad(InfoCadInput(cnpj=None, verbose=False, page=1, page_size=19))

    assert outcome.status == "error"
    assert outcome.message is not None
    assert "entre 20 e 1000" in outcome.message
