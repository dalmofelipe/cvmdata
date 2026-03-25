"""Testes unitários dos handlers e modelos do módulo CLI."""

from __future__ import annotations

import pytest

from cvmdata.cli.handlers import download, indicators, load, normalize, query
from cvmdata.cli.models import (
    DownloadInput,
    IndicatorsInput,
    LoadInput,
    NormalizeInput,
    Outcome,
    QueryInput,
    QueryResult,
)

# ============================================================================
# Models / Outcome
# ============================================================================


def test_outcome_factories() -> None:
    """Valida factories de Outcome para sucesso/aviso/erro."""
    ok = Outcome.success(message="ok", payload={"a": 1})
    warn = Outcome.warning(message="warn")
    err = Outcome.error(message="err")

    assert ok.status == "success"
    assert ok.payload == {"a": 1}
    assert warn.status == "warning"
    assert warn.payload is None
    assert err.status == "error"
    assert err.payload is None


def test_input_models_instantiation() -> None:
    """Instancia modelos de entrada e de linha de query."""
    d = DownloadInput(years=[2024], force=False, verbose=True)
    load_input = LoadInput(years=[2024], verbose=False)
    n = NormalizeInput(verbose=True)
    i = IndicatorsInput(cnpj="00.000.000/0001-91", verbose=False)
    q = QueryInput(cnpj=None, year=2024)
    r = QueryResult(cnpj_cia="00.000.000/0001-91")

    assert d.years == [2024]
    assert load_input.verbose is False
    assert n.verbose is True
    assert i.cnpj == "00.000.000/0001-91"
    assert q.year == 2024
    assert r.cnpj_cia == "00.000.000/0001-91"


# ============================================================================
# Download handler (T037)
# ============================================================================


def test_download_handler_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retorna sucesso quando há CSVs baixados."""

    def fake_download(*args, **kwargs):
        return ["a.csv", "b.csv"]

    monkeypatch.setattr(download, "download_source_year", fake_download)

    outcome = download.handle(DownloadInput(years=[2024], force=False, verbose=False))

    assert outcome.status == "success"
    assert outcome.payload is not None
    assert outcome.payload["itr_2024"] == 2
    assert outcome.payload["dfp_2024"] == 2


def test_download_handler_warning_when_no_new_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retorna warning quando não há novos arquivos para baixar."""

    def fake_download(*args, **kwargs):
        return []

    monkeypatch.setattr(download, "download_source_year", fake_download)

    outcome = download.handle(DownloadInput(years=[2024], force=False, verbose=False))

    assert outcome.status == "warning"
    assert "CSV" in (outcome.message or "")


def test_download_handler_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retorna erro quando falha no downloader."""

    def fake_download(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(download, "download_source_year", fake_download)

    outcome = download.handle(DownloadInput(years=[2024], force=True, verbose=False))

    assert outcome.status == "error"
    assert "Falha no download" in (outcome.message or "")


# ============================================================================
# Load handler (T038)
# ============================================================================


def test_load_handler_success(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna sucesso somando linhas por source/ano."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_load_source_year(_conn, _source, _year, _raw_dir):
        return {"BPA/con": 10, "BPP/con": 5}

    monkeypatch.setattr(load, "get_connection", fake_get_connection)
    monkeypatch.setattr(load, "load_source_year", fake_load_source_year)

    outcome = load.handle(LoadInput(years=[2024], verbose=False))

    assert outcome.status == "success"
    assert outcome.payload == {"itr_2024": 15, "dfp_2024": 15}


def test_load_handler_warning_no_files(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna warning quando não há CSV para carregar."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_load_source_year(_conn, _source, _year, _raw_dir):
        return {}

    monkeypatch.setattr(load, "get_connection", fake_get_connection)
    monkeypatch.setattr(load, "load_source_year", fake_load_source_year)

    outcome = load.handle(LoadInput(years=[2024], verbose=False))

    assert outcome.status == "warning"


def test_load_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna erro quando o loader falha."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_load_source_year(_conn, _source, _year, _raw_dir):
        raise RuntimeError("broken csv")

    monkeypatch.setattr(load, "get_connection", fake_get_connection)
    monkeypatch.setattr(load, "load_source_year", fake_load_source_year)

    outcome = load.handle(LoadInput(years=[2024], verbose=False))

    assert outcome.status == "error"


# ============================================================================
# Normalize handler (T039)
# ============================================================================


def test_normalize_handler_success(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna sucesso quando normalização produz tabelas."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_normalize_all(_conn):
        return {"raw_bpa_clean": 10, "raw_bpp_clean": 20}

    monkeypatch.setattr(normalize, "get_connection", fake_get_connection)
    monkeypatch.setattr(normalize, "normalize_all", fake_normalize_all)

    outcome = normalize.handle(NormalizeInput(verbose=True))

    assert outcome.status == "success"
    assert outcome.payload == {"raw_bpa_clean": 10, "raw_bpp_clean": 20}


def test_normalize_handler_warning_no_input(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna warning quando não há tabelas raw_* para normalizar."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    monkeypatch.setattr(normalize, "get_connection", fake_get_connection)
    monkeypatch.setattr(normalize, "normalize_all", lambda _conn: {})

    outcome = normalize.handle(NormalizeInput(verbose=False))

    assert outcome.status == "warning"


def test_normalize_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna erro quando normalize_all lança exceção."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_normalize_all(_conn):
        raise RuntimeError("duckdb error")

    monkeypatch.setattr(normalize, "get_connection", fake_get_connection)
    monkeypatch.setattr(normalize, "normalize_all", fake_normalize_all)

    outcome = normalize.handle(NormalizeInput(verbose=False))

    assert outcome.status == "error"


# ============================================================================
# Indicators handler (T040)
# ============================================================================


def test_indicators_handler_success_with_cnpj(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna sucesso com filtro de CNPJ."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_calculate_all(_conn, cnpj=None):
        assert cnpj == "00.000.000/0001-91"
        return 12

    monkeypatch.setattr(indicators, "get_connection", fake_get_connection)
    monkeypatch.setattr(indicators, "calculate_all", fake_calculate_all)

    outcome = indicators.handle(IndicatorsInput(cnpj="00.000.000/0001-91", verbose=False))

    assert outcome.status == "success"
    assert outcome.payload == 12


def test_indicators_handler_warning_when_zero(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna warning quando total calculado é zero."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    monkeypatch.setattr(indicators, "get_connection", fake_get_connection)
    monkeypatch.setattr(indicators, "calculate_all", lambda _conn, cnpj=None: 0)

    outcome = indicators.handle(IndicatorsInput(cnpj=None, verbose=False))

    assert outcome.status == "warning"


def test_indicators_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna erro em falha no cálculo."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_calculate_all(_conn, cnpj=None):
        raise RuntimeError("calc failed")

    monkeypatch.setattr(indicators, "get_connection", fake_get_connection)
    monkeypatch.setattr(indicators, "calculate_all", fake_calculate_all)

    outcome = indicators.handle(IndicatorsInput(cnpj=None, verbose=False))

    assert outcome.status == "error"


# ============================================================================
# Query handler (T041)
# ============================================================================


def test_query_handler_success_summary(
    monkeypatch: pytest.MonkeyPatch,
    cli_test_db,
    connection_context_factory,
) -> None:
    """Retorna resumo quando consulta é sem CNPJ."""

    def fake_get_connection(_):
        return connection_context_factory(cli_test_db)

    monkeypatch.setattr(query, "get_connection", fake_get_connection)

    outcome = query.handle(QueryInput(cnpj=None, year=None))

    assert outcome.status == "success"
    assert outcome.payload
    assert outcome.payload[0].n_indicadores is not None


def test_query_handler_success_detail(
    monkeypatch: pytest.MonkeyPatch,
    cli_test_db,
    connection_context_factory,
) -> None:
    """Retorna detalhe quando consulta é filtrada por CNPJ."""

    def fake_get_connection(_):
        return connection_context_factory(cli_test_db)

    monkeypatch.setattr(query, "get_connection", fake_get_connection)

    outcome = query.handle(QueryInput(cnpj="00.000.000/0001-91", year=2024))

    assert outcome.status == "success"
    assert outcome.payload
    assert outcome.payload[0].indicador is not None


def test_query_handler_warning_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    cli_test_db,
    connection_context_factory,
) -> None:
    """Retorna warning quando não há resultado para o filtro."""

    def fake_get_connection(_):
        return connection_context_factory(cli_test_db)

    monkeypatch.setattr(query, "get_connection", fake_get_connection)

    outcome = query.handle(QueryInput(cnpj="99.999.999/0001-99", year=2024))

    assert outcome.status == "warning"


def test_query_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna erro quando a consulta ao banco falha."""

    class BrokenConn:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("query failed")

    def fake_get_connection(_):
        return connection_context_factory(BrokenConn())

    monkeypatch.setattr(query, "get_connection", fake_get_connection)

    outcome = query.handle(QueryInput(cnpj=None, year=None))

    assert outcome.status == "error"
