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


def run_full(
    *,
    years: list[int],
    force_download: bool = False,
    cnpj: str | None = None,
    data_dir: Path | None = None,
    db_path: Path | None = None,
) -> PipelineReport:
    """Executa o pipeline completo.

    Este é o ponto único de orquestração. CLI/cron/scripts devem chamar aqui.

    Observação: idempotência e bulk ops são garantidas pelas funções do core
    (downloader/loader/normalize/indicators/info_cad). Este orquestrador só
    define ordem, compõe parâmetros e reporta execução.
    """
    years = years or settings.years_list

    started_at = _now()
    step_reports: list[StepReport] = []

    effective_data_dir = data_dir or settings.data_dir
    effective_db_path = db_path or settings.db_path

    cad_csv_path: Path | None = None
    b3_tickers_dir = settings.b3_tickers_dir

    try:
        # Download financeiro (ITR/DFP)
        step_reports.append(step_downloads_cvm(years, force_download, effective_data_dir))

        # Download cadastral
        cad_csv_path, s2 = step_download_info_cad(force_download, effective_data_dir)
        step_reports.append(s2)

        with get_connection(effective_db_path) as conn:
            # Load opcional de tickers B3
            step_reports.append(step_load_b3_tickers(conn, b3_tickers_dir))

            # Load cadastral
            step_reports.append(step_load_info_cad(conn, cad_csv_path))

            # Load financeiro
            step_reports.append(step_load_cvm(conn, years, effective_data_dir))

            # Classificação cadastral
            step_reports.append(step_classify_info_cad(conn))

            # Normalize
            step_reports.append(step_normalize_financial(conn))

            # Indicators
            step_reports.append(step_calculate_indicators(conn, cnpj))

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
