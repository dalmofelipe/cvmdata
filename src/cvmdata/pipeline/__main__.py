from __future__ import annotations

import argparse

from cvmdata.config import settings
from cvmdata.pipeline.orchestrator import run_full
from cvmdata.pipeline.years import parse_years


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m cvmdata.pipeline")
    parser.add_argument(
        "--years",
        help="Ano, lista ou intervalo (ex: 2024 | 2021,2022,2024 | 2021:2025)",
    )
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--cnpj", help="Filtrar cálculo de indicadores por CNPJ")
    args = parser.parse_args()

    years = parse_years(args.years) if args.years else list(settings.years)
    report = run_full(
        years=years,
        force_download=args.force_download,
        cnpj=args.cnpj,
    )

    # Minimal stdout report
    print(f"pipeline={report.name} status={report.status}")
    for step in report.steps:
        print(f"- {step.name}: {step.status} {step.message or ''}".rstrip())


if __name__ == "__main__":
    main()
