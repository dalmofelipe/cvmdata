from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

StepStatus = Literal["success", "warning", "error", "skipped"]


@dataclass(frozen=True)
class StepReport:
    name: str
    status: StepStatus
    message: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class PipelineReport:
    name: str
    status: StepStatus
    steps: list[StepReport]
    started_at: datetime
    finished_at: datetime


class PipelineExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        report: PipelineReport | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.report = report
        self.cause = cause
