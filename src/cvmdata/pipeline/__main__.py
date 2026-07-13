from __future__ import annotations

import logging

from cvmdata.config import settings
from cvmdata.pipeline.orchestrator import run_full


def main() -> None:
    level = logging.DEBUG if settings.verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )

    report = run_full(
        years=settings.years_list,
        force_download=settings.force_download,
        cnpj=settings.cnpj,
    )

    print(f"pipeline={report.name} status={report.status}")
    for step in report.steps:
        print(f"- {step.name}: {step.status} {step.message or ''}".rstrip())

    raise SystemExit(0 if report.status != "error" else 1)


if __name__ == "__main__":
    main()
