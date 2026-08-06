import logging
from datetime import datetime, timezone
from pathlib import Path

from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.pipeline.models import PipelineExecutionError, PipelineReport, StepReport
from cvmdata.pipeline.steps import (
    step_calculate_indicators,
    step_classify_info_cad,
    step_download_info_cad,
    step_downloads_cvm,
    step_load_b3_tickers,
    step_load_cvm,
    step_load_info_cad,
    step_normalize_financial,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _coalesce(val, default_factory):
    return val if val is not None else default_factory()


def run_full(
    *,
    years: list[int],
    force_download: bool = False,
    cnpj: str | None = None,
    data_dir: Path | None = None,
    db_path: Path | None = None,
    duckdb_memory_limit: str | None = None,
    duckdb_threads: int | None = None,
    b3_tickers_dir: Path | None = None,
) -> PipelineReport:
    """Executa o pipeline completo"""

    # Resolvendo os fallbacks para as configurações do Settings
    effective_years = _coalesce(years, lambda: settings.years_list)
    effective_force = _coalesce(force_download, lambda: settings.force_download)
    effective_cnpj = _coalesce(cnpj, lambda: settings.cnpj)
    effective_data_dir = _coalesce(data_dir, lambda: settings.data_dir)
    effective_db_path = _coalesce(db_path, lambda: settings.db_path)
    effective_memory = _coalesce(duckdb_memory_limit, lambda: settings.sanitized_duckdb_memory_limit)
    effective_threads = _coalesce(duckdb_threads, lambda: settings.sanitized_duckdb_threads)
    effective_b3_dir = _coalesce(b3_tickers_dir, lambda: settings.b3_tickers_dir)

    started_at = _now()
    step_reports: list[StepReport] = []
    cad_csv_path: Path | None = None

    try:
        # Download financeiro (ITR/DFP)
        step_reports.append(step_downloads_cvm(effective_years, effective_force, effective_data_dir))

        # Download cadastral
        cad_csv_path, s2 = step_download_info_cad(effective_force, effective_data_dir)
        step_reports.append(s2)

        with get_connection(
            db_path=effective_db_path, 
            memory_limit=effective_memory, 
            threads=effective_threads
        ) as conn:

            # Load opcional de tickers B3
            step_reports.append(step_load_b3_tickers(conn, effective_b3_dir))

            # Load cadastral
            step_reports.append(step_load_info_cad(conn, cad_csv_path))

            # Load financeiro
            step_reports.append(step_load_cvm(conn, effective_years, effective_data_dir))

            # Classificação cadastral
            step_reports.append(step_classify_info_cad(conn))

            # Normalize
            step_reports.append(step_normalize_financial(conn))

            # Indicators
            step_reports.append(step_calculate_indicators(conn, effective_cnpj))

        # Status global
        statuses = [s.status for s in step_reports]
        overall = "error" if "error" in statuses else "warning" if "warning" in statuses else "success"
        finished_at = _now()

        return PipelineReport(
            name="full", status=overall, steps=step_reports, started_at=started_at, finished_at=finished_at
        )

    except Exception as exc:
        finished_at = _now()
        report = PipelineReport(
            name="full", status="error", steps=step_reports, started_at=started_at, finished_at=finished_at
        )
        logger.exception("Falha no pipeline full")
        raise PipelineExecutionError("Falha ao executar pipeline full", report=report, cause=exc) from exc
