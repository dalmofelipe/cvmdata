"""Testes unitários dos handlers e modelos do módulo CLI."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from cvmdata.cli.handlers.ingestion import download, indicators, load, normalize, query
from cvmdata.cli.handlers.transform import classify_info_cad, download_info_cad, load_info_cad, query_info_cad
from cvmdata.cli.models import (
    ClassifyInfoCadInput,
    ClassifyInfoCadResult,
    DownloadInfoCadInput,
    DownloadInput,
    IndicatorsInput,
    LoadInfoCadInput,
    LoadInput,
    NormalizeInput,
    Outcome,
    QueryInfoCadInput,
    QueryInfoCadResult,
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


# ============================================================================
# Download Informação Cadastral Handler
# ============================================================================


def test_download_info_cad_handler_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Retorna sucesso quando download de informacao cadastral funciona."""
    meta_file = tmp_path / "cad_cia_aberta.meta"
    csv_file = tmp_path / "cad_cia_aberta.csv"
    meta_file.write_text("meta content")
    csv_file.write_text("cnpj,name\n00.000.000/0001-91,Banco X")

    def fake_download(*args, **kwargs):
        return (meta_file, csv_file)

    monkeypatch.setattr(download_info_cad, "download_info_cad", fake_download)

    outcome = download_info_cad.handle(DownloadInfoCadInput(force=False, verbose=False))

    assert outcome.status == "success"
    assert outcome.payload is not None
    assert outcome.payload["csv_file"] == "cad_cia_aberta.csv"
    assert outcome.payload["csv_size_bytes"] > 0


def test_download_cad_handler_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retorna erro quando download falha."""

    def fake_download(*args, **kwargs):
        raise FileNotFoundError("CVM server down")

    monkeypatch.setattr(download_info_cad, "download_info_cad", fake_download)

    outcome = download_info_cad.handle(DownloadInfoCadInput(force=True, verbose=False))

    assert outcome.status == "error"
    assert "cadastrais" in (outcome.message or "")


# ============================================================================
# Load Informação Cadastral Handler
# ============================================================================


def test_load_info_cad_handler_success(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
    tmp_path,
) -> None:
    """Retorna sucesso quando carregamento da informacao cadastral funciona."""
    csv_path = tmp_path / "cad_cia_aberta.csv"
    csv_path.write_text("cnpj,name\n00.000.000/0001-91,Banco X\n")

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_load_info_cad(_conn, _path):
        return 1

    monkeypatch.setattr(
        load_info_cad,
        "settings",
        SimpleNamespace(cad_dir=tmp_path, db_path=":memory:"),
    )
    monkeypatch.setattr(load_info_cad, "get_connection", fake_get_connection)
    monkeypatch.setattr(load_info_cad, "load_info_cad", fake_load_info_cad)

    outcome = load_info_cad.handle(LoadInfoCadInput(verbose=False))

    assert outcome.status == "success"
    assert outcome.payload == 1


def test_load_info_cad_handler_warning_file_not_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Retorna warning quando arquivo cadastral não existe."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    monkeypatch.setattr(
        load_info_cad,
        "settings",
        SimpleNamespace(cad_dir=empty_dir, db_path=":memory:"),
    )

    outcome = load_info_cad.handle(LoadInfoCadInput(verbose=False))

    assert outcome.status == "warning"
    assert "não encontrado" in (outcome.message or "")


def test_load_info_cad_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
    tmp_path,
) -> None:
    """Retorna erro quando load_info_cad falha."""
    csv_path = tmp_path / "cad_cia_aberta.csv"
    csv_path.write_text("cnpj,name\n00.000.000/0001-91,Banco X\n")

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_load_info_cad(_conn, _path):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(
        load_info_cad,
        "settings",
        SimpleNamespace(cad_dir=tmp_path, db_path=":memory:"),
    )
    monkeypatch.setattr(load_info_cad, "get_connection", fake_get_connection)
    monkeypatch.setattr(load_info_cad, "load_info_cad", fake_load_info_cad)

    outcome = load_info_cad.handle(LoadInfoCadInput(verbose=False))

    assert outcome.status == "error"
    assert "Falha" in (outcome.message or "")


# ============================================================================
# Classify Informação Cadastral Handler
# ============================================================================


def test_classify_info_cad_handler_success(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna sucesso com contagens classificadas."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_classify(_conn):
        return {"total": 100, "high": 60, "low": 40}

    monkeypatch.setattr(classify_info_cad, "get_connection", fake_get_connection)
    monkeypatch.setattr(classify_info_cad, "classify_info_cad", fake_classify)

    outcome = classify_info_cad.handle(ClassifyInfoCadInput(verbose=False))

    assert outcome.status == "success"
    assert isinstance(outcome.payload, ClassifyInfoCadResult)
    assert outcome.payload.total == 100
    assert outcome.payload.high == 60
    assert outcome.payload.low == 40


def test_classify_info_cad_handler_warning_not_loaded(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna warning quando cad_cia_aberta_raw não foi carregada."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_classify(_conn):
        raise RuntimeError("table cad_cia_aberta_raw not found")

    monkeypatch.setattr(classify_info_cad, "get_connection", fake_get_connection)
    monkeypatch.setattr(classify_info_cad, "classify_info_cad", fake_classify)

    outcome = classify_info_cad.handle(ClassifyInfoCadInput(verbose=False))

    assert outcome.status == "warning"


def test_classify_info_cad_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna erro quando classificação falha."""

    def fake_get_connection(_):
        return connection_context_factory(object())

    def fake_classify(_conn):
        raise ValueError("unexpected error")

    monkeypatch.setattr(classify_info_cad, "get_connection", fake_get_connection)
    monkeypatch.setattr(classify_info_cad, "classify_info_cad", fake_classify)

    outcome = classify_info_cad.handle(ClassifyInfoCadInput(verbose=False))

    assert outcome.status == "error"
    assert "Falha" in (outcome.message or "")


# ============================================================================
# Query Informação Cadastral Handler
# ============================================================================


def test_query_info_cad_handler_summary_success(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna resumo (últimas 20 classificações) sem filtro de CNPJ."""

    class MockConn:
        def execute(self, sql, params=None):
            return self

        def fetchall(self):
            # Simula resposta de query summary (6 colunas)
            return [
                ("00.000.000/0001-91", "Banco X", "Financial", "high", 0.95, "2024-01-01"),
                ("11.111.111/0001-11", "Banco Y", "Financial", "low", 0.45, "2024-01-01"),
            ]

    def fake_get_connection(_):
        return connection_context_factory(MockConn())

    monkeypatch.setattr(query_info_cad, "get_connection", fake_get_connection)

    outcome = query_info_cad.handle(QueryInfoCadInput(cnpj=None, verbose=False))

    assert outcome.status == "success"
    assert outcome.payload is not None
    assert len(outcome.payload) == 2
    assert all(isinstance(r, QueryInfoCadResult) for r in outcome.payload)
    assert outcome.payload[0].cnpj_cia == "00.000.000/0001-91"


def test_query_info_cad_handler_detail_success(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna detalhe completo para um CNPJ específico."""

    class MockConn:
        def execute(self, sql, params=None):
            return self

        def fetchall(self):
            # Simula resposta de query detail (9 colunas)
            return [
                (
                    "00.000.000/0001-91",
                    "12345",
                    "Banco X",
                    "Banco X Comercial",
                    "Financial",
                    "high",
                    0.95,
                    "rule_finance_01",
                    "2024-01-01",
                ),
            ]

    def fake_get_connection(_):
        return connection_context_factory(MockConn())

    monkeypatch.setattr(query_info_cad, "get_connection", fake_get_connection)

    outcome = query_info_cad.handle(QueryInfoCadInput(cnpj="00.000.000/0001-91", verbose=False))

    assert outcome.status == "success"
    assert outcome.payload is not None
    assert len(outcome.payload) == 1
    assert outcome.payload[0].cd_cvm == "12345"
    assert outcome.payload[0].denom_comerc == "Banco X Comercial"


def test_query_info_cad_handler_warning_not_found(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna warning quando não há classificações para o CNPJ."""

    class MockConn:
        def execute(self, sql, params=None):
            return self

        def fetchall(self):
            return []

    def fake_get_connection(_):
        return connection_context_factory(MockConn())

    monkeypatch.setattr(query_info_cad, "get_connection", fake_get_connection)

    outcome = query_info_cad.handle(QueryInfoCadInput(cnpj="99.999.999/0001-99", verbose=False))

    assert outcome.status == "warning"
    assert "encontrada" in (outcome.message or "")


def test_query_info_cad_handler_error(
    monkeypatch: pytest.MonkeyPatch,
    connection_context_factory,
) -> None:
    """Retorna erro quando a consulta ao banco falha."""

    class BrokenConn:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("query failed")

    def fake_get_connection(_):
        return connection_context_factory(BrokenConn())

    monkeypatch.setattr(query_info_cad, "get_connection", fake_get_connection)

    outcome = query_info_cad.handle(QueryInfoCadInput(cnpj=None, verbose=False))

    assert outcome.status == "error"
    assert "Falha" in (outcome.message or "")
