from __future__ import annotations

import logging

from cvmdata.config import settings
from cvmdata.pipeline.orchestrator import run_full
from cvmdata.utils.database import DuckDBValidationError
from cvmdata.utils.years import YearsParseError


def main() -> None:

    level = logging.DEBUG if settings.verbose else logging.INFO

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )

    try:
        years = settings.years_list
        duckdb_memory_limit = settings.sanitized_duckdb_memory_limit
        duckdb_threads = settings.sanitized_duckdb_threads

    except YearsParseError as exc:
        print(f"Configuração inválida (CVM_YEARS): {exc}")
        raise SystemExit(2) from None
    
    except DuckDBValidationError as exc:
        print(exc)
        raise SystemExit(2) from None

    report = run_full(
        years=years,
        duckdb_memory_limit=duckdb_memory_limit,
        duckdb_threads=duckdb_threads
    )

    print(f"pipeline={report.name} status={report.status}")
    for step in report.steps:
        print(f"- {step.name}: {step.status} {step.message or ''}".rstrip())

    raise SystemExit(0 if report.status != "error" else 1)


if __name__ == "__main__":
    main()
