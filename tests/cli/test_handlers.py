# Unit tests for handlers
import pytest

from cvmdata.cli.models import (
    Outcome,
    DownloadInput,
    LoadInput,
    NormalizeInput,
    IndicatorsInput,
    QueryInput,
    QueryResult,
)


# ============================================================================
# Tests for Outcome[T] Factory Methods (T018)
# ============================================================================

def test_outcome_success_with_message_and_payload():
    """Outcome.success() creates outcome with status='success'."""
    payload = {"itr_2024": 3, "dfp_2024": 3}
    msg = "Downloaded 6 CSVs"
    outcome = Outcome.success(message=msg, payload=payload)
    
    assert outcome.status == "success"
    assert outcome.message == msg
    assert outcome.payload == payload


def test_outcome_success_with_message_only():
    """Outcome.success() works with message only."""
    msg = "Normalized 4 tables"
    outcome = Outcome.success(message=msg)
    
    assert outcome.status == "success"
    assert outcome.message == msg
    assert outcome.payload is None


def test_outcome_success_empty():
    """Outcome.success() can be called with no args."""
    outcome = Outcome.success()
    
    assert outcome.status == "success"
    assert outcome.message is None
    assert outcome.payload is None


def test_outcome_warning_with_payload():
    """Outcome.warning() creates outcome with status='warning'."""
    msg = "No data found"
    payload = {}
    outcome = Outcome.warning(message=msg, payload=payload)
    
    assert outcome.status == "warning"
    assert outcome.message == msg
    assert outcome.payload == payload


def test_outcome_warning_without_payload():
    """Outcome.warning() works without payload."""
    msg = "No files downloaded"
    outcome = Outcome.warning(message=msg)
    
    assert outcome.status == "warning"
    assert outcome.message == msg
    assert outcome.payload is None


def test_outcome_error():
    """Outcome.error() creates outcome with status='error' and no payload."""
    msg = "Invalid year (must be 2000-3000)"
    outcome = Outcome.error(message=msg)
    
    assert outcome.status == "error"
    assert outcome.message == msg
    assert outcome.payload is None


def test_outcome_error_ignores_payload():
    """Outcome.error() always returns payload=None even if provided."""
    outcome = Outcome.error(message="Error")
    assert outcome.payload is None


# ============================================================================
# Tests for Input Dataclasses (T018)
# ============================================================================

def test_download_input_instantiation():
    """DownloadInput accepts all required fields."""
    inp = DownloadInput(years=[2024, 2025], force=True, verbose=False)
    
    assert inp.years == [2024, 2025]
    assert inp.force is True
    assert inp.verbose is False


def test_load_input_instantiation():
    """LoadInput accepts all required fields."""
    inp = LoadInput(years=[2024], verbose=True)
    
    assert inp.years == [2024]
    assert inp.verbose is True


def test_normalize_input_instantiation():
    """NormalizeInput accepts verbose flag."""
    inp = NormalizeInput(verbose=False)
    
    assert inp.verbose is False


def test_indicators_input_with_cnpj():
    """IndicatorsInput accepts CNPJ filter."""
    inp = IndicatorsInput(cnpj="00.000.000/0001-00", verbose=True)
    
    assert inp.cnpj == "00.000.000/0001-00"
    assert inp.verbose is True


def test_indicators_input_without_cnpj():
    """IndicatorsInput works with cnpj=None."""
    inp = IndicatorsInput(cnpj=None, verbose=False)
    
    assert inp.cnpj is None
    assert inp.verbose is False


def test_query_input_with_filters():
    """QueryInput accepts CNPJ and year filters."""
    inp = QueryInput(cnpj="00.000.000/0001-00", year=2024)
    
    assert inp.cnpj == "00.000.000/0001-00"
    assert inp.year == 2024


def test_query_input_without_filters():
    """QueryInput works without filters."""
    inp = QueryInput(cnpj=None, year=None)
    
    assert inp.cnpj is None
    assert inp.year is None


# ============================================================================
# Tests for QueryResult Dataclass (T018)
# ============================================================================

def test_query_result_summary_row():
    """QueryResult can represent summary query row."""
    row = QueryResult(
        cnpj_cia="00.000.000/0001-00",
        n_indicadores=42,
        primeiro_periodo="2021-01-01",
        ultimo_periodo="2024-12-31",
    )
    
    assert row.cnpj_cia == "00.000.000/0001-00"
    assert row.n_indicadores == 42
    assert row.primeiro_periodo == "2021-01-01"
    assert row.ultimo_periodo == "2024-12-31"
    assert row.indicador is None


def test_query_result_detail_row():
    """QueryResult can represent detail query row."""
    row = QueryResult(
        cnpj_cia="00.000.000/0001-00",
        dt_refer="2024-12-31",
        indicador="ROE",
        valor=0.1234,
    )
    
    assert row.cnpj_cia == "00.000.000/0001-00"
    assert row.dt_refer == "2024-12-31"
    assert row.indicador == "ROE"
    assert row.valor == 0.1234
    assert row.n_indicadores is None


def test_query_result_minimal():
    """QueryResult can be instantiated with just cnpj_cia."""
    row = QueryResult(cnpj_cia="00.000.000/0001-00")
    
    assert row.cnpj_cia == "00.000.000/0001-00"
    assert row.dt_refer is None
    assert row.indicador is None
    assert row.valor is None
    assert row.n_indicadores is None

