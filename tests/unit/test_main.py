from __future__ import annotations

from types import SimpleNamespace

import pytest

from cvmdata.pipeline import __main__ as main_module
from cvmdata.pipeline.models import PipelineReport, StepReport
from cvmdata.utils.database import DuckDBValidationError
from cvmdata.utils.years import YearsParseError

pytestmark = pytest.mark.unit


def _report(status: str) -> PipelineReport:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return PipelineReport(
        name="full",
        status=status,
        steps=[StepReport("step", status)],
        started_at=now,
        finished_at=now,
    )


def test_main_exits_zero_for_success(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            verbose=False,
            years_list=[2024],
            sanitized_duckdb_memory_limit=None,
            sanitized_duckdb_threads=None,
        ),
    )
    monkeypatch.setattr(main_module, "run_full", lambda **kwargs: _report("success"))

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == 0


def test_main_exits_one_for_pipeline_error_status(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            verbose=False,
            years_list=[2024],
            sanitized_duckdb_memory_limit=None,
            sanitized_duckdb_threads=None,
        ),
    )
    monkeypatch.setattr(main_module, "run_full", lambda **kwargs: _report("error"))

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == 1


@pytest.mark.parametrize(
    "error",
    [YearsParseError("bad"), DuckDBValidationError("threads", 0, "invalid")],
)
def test_main_exits_two_for_invalid_configuration(monkeypatch, error):
    class _Settings:
        verbose = False
        sanitized_duckdb_memory_limit = None
        sanitized_duckdb_threads = None

        @property
        def years_list(self):
            raise error

    monkeypatch.setattr(main_module, "settings", _Settings())

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == 2
