from contextlib import contextmanager
from pathlib import Path

import pytest

from cvmdata.pipeline.models import PipelineExecutionError, StepReport
from cvmdata.pipeline.orchestrator import run_full

pytestmark = pytest.mark.unit


class _FakeConn:
    pass


@contextmanager
def _fake_connection(db_path, memory_limit=None, threads=None):
    yield _FakeConn()


def test_run_full_reports_b3_tickers_step(monkeypatch, tmp_path):
    from cvmdata.pipeline import orchestrator as orchestrator_module
    from cvmdata.pipeline import steps as steps_module

    monkeypatch.setattr(
        orchestrator_module, "get_connection", _fake_connection)
    
    monkeypatch.setattr(
        steps_module, "download_source_year",lambda *args, **kwargs: [Path("dummy.csv")])
    monkeypatch.setattr(
        steps_module, "download_info_cad", lambda *args, 
            **kwargs: (tmp_path / "meta.txt", tmp_path / "cad.csv"))
    monkeypatch.setattr(
        steps_module, "load_b3_tickers", lambda *args, **kwargs: 3)
    monkeypatch.setattr(
        steps_module, "load_info_cad", lambda *args, **kwargs: 11)
    monkeypatch.setattr(
        steps_module, "load_source_year", lambda *args, **kwargs: {"BPA/con": 5})
    monkeypatch.setattr(
        steps_module, "classify_info_cad", lambda *args, **kwargs: {"total": 11})
    monkeypatch.setattr(
        steps_module, "normalize_all", lambda *args, **kwargs: {"raw_bpa": 5})
    monkeypatch.setattr(
        steps_module, "calculate_all", lambda *args, **kwargs: 7)
    
    (tmp_path / "meta.txt").write_text("meta", encoding="utf-8")
    (tmp_path / "cad.csv").write_text("col1;col2\n1;2\n", encoding="utf-8")

    report = run_full(years=[2024], force_download=False, cnpj=None)

    step_names = [step.name for step in report.steps]
    assert step_names[0] == "download_financial"
    assert "load_b3_tickers" in step_names
    assert step_names.index("load_b3_tickers") < step_names.index("load_financial")
    assert step_names.index("normalize_financial") < step_names.index("classify_info_cad")
    assert report.status == "success"


def test_run_full_aggregates_warning_status(monkeypatch, tmp_path):
    from cvmdata.pipeline import orchestrator as orchestrator_module

    monkeypatch.setattr(
        orchestrator_module, "get_connection", _fake_connection)
    warning = StepReport(
        name="download_financial", status="warning")
    monkeypatch.setattr(
        orchestrator_module, "step_downloads_cvm", lambda *a: warning)
    monkeypatch.setattr(
        orchestrator_module,
        "step_download_info_cad",
        lambda *a: (tmp_path / "cad.csv", StepReport("download_info_cad", "success")),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "step_load_b3_tickers",
        lambda *a: StepReport("load_b3_tickers", "success"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "step_load_info_cad",
        lambda *a: StepReport("load_info_cad", "success"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "step_load_cvm",
        lambda *a: StepReport("load_financial", "success"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "step_normalize_financial",
        lambda *a: StepReport("normalize_financial", "success"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "step_classify_info_cad",
        lambda *a: StepReport("classify_info_cad", "success"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "step_calculate_indicators",
        lambda *a: StepReport("indicators", "success"),
    )

    report = run_full(years=[2024], data_dir=tmp_path, db_path=tmp_path / "db.duckdb")

    assert report.status == "warning"


def test_run_full_wraps_step_failure(monkeypatch):
    from cvmdata.pipeline import orchestrator as orchestrator_module

    monkeypatch.setattr(
        orchestrator_module,
        "step_downloads_cvm",
        lambda *a: (_ for _ in ()).throw(RuntimeError("download failed")),
    )

    with pytest.raises(PipelineExecutionError) as exc_info:
        run_full(years=[2024])

    error = exc_info.value
    assert error.cause.args == ("download failed",)
    assert error.report is not None
    assert error.report.status == "error"
