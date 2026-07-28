from contextlib import contextmanager
from pathlib import Path

from cvmdata.pipeline.orchestrator import run_full


class _FakeConn:
    pass


@contextmanager
def _fake_connection(db_path):
    yield _FakeConn()


def test_run_full_reports_b3_tickers_step(monkeypatch, tmp_path):
    from cvmdata.pipeline import orchestrator as orchestrator_module
    from cvmdata.pipeline import steps as steps_module

    monkeypatch.setattr(orchestrator_module, "get_connection", _fake_connection)
    monkeypatch.setattr(
        steps_module,
        "download_source_year",
        lambda *args, **kwargs: [Path("dummy.csv")],
    )
    monkeypatch.setattr(steps_module, "load_b3_tickers", lambda *args, **kwargs: 3)
    monkeypatch.setattr(
        steps_module,
        "load_source_year",
        lambda *args, **kwargs: {"BPA/con": 5},
    )
    monkeypatch.setattr(
        steps_module,
        "normalize_all",
        lambda *args, **kwargs: {"raw_bpa": 5},
    )
    monkeypatch.setattr(steps_module, "calculate_all", lambda *args, **kwargs: 7)
    monkeypatch.setattr(
        steps_module,
        "download_info_cad",
        lambda *args, **kwargs: (tmp_path / "meta.txt", tmp_path / "cad.csv"),
    )
    (tmp_path / "meta.txt").write_text("meta", encoding="utf-8")
    (tmp_path / "cad.csv").write_text("col1;col2\n1;2\n", encoding="utf-8")
    monkeypatch.setattr(steps_module, "load_info_cad", lambda *args, **kwargs: 11)
    monkeypatch.setattr(
        steps_module,
        "classify_info_cad",
        lambda *args, **kwargs: {"total": 11},
    )

    report = run_full(years=[2024], force_download=False, cnpj=None)

    step_names = [step.name for step in report.steps]
    assert step_names[0] == "download_financial"
    assert "load_b3_tickers" in step_names
    assert step_names.index("load_b3_tickers") < step_names.index("load_financial")
    assert report.status == "success"