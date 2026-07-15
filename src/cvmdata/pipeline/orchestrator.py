from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.ingestion.downloader import download_info_cad, download_source_year
from cvmdata.ingestion.loader import load_b3_tickers, load_info_cad, load_source_year
from cvmdata.pipeline.models import PipelineExecutionError, PipelineReport, StepReport
from cvmdata.transform.indicators import calculate_all
from cvmdata.transform.info_cad import classify_info_cad
from cvmdata.transform.normalize import normalize_all

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

    meta_path: Path | None = None
    cad_csv_path: Path | None = None
    b3_tickers_dir = settings.b3_tickers_dir

    try:
        # Download financeiro (ITR/DFP)
        s0 = _now()
        downloaded_counts: dict[str, int] = {}
        for year in years:
            for source, url_template in (
                ("itr", settings.itr_url_template),
                ("dfp", settings.dfp_url_template),
            ):
                extracted = download_source_year(
                    source,
                    year,
                    url_template,
                    effective_data_dir / "raw",
                    force=force_download,
                )
                downloaded_counts[f"{source}_{year}"] = len(extracted)
        step_reports.append(
            StepReport(
                name="download_financial",
                status="success" if any(downloaded_counts.values()) else "warning",
                message=(
                    "ZIPs processados e CSVs extraídos"
                    if any(downloaded_counts.values())
                    else "Nenhum CSV novo extraído (provável cache local)"
                ),
                metrics=downloaded_counts,
                started_at=s0,
                finished_at=_now(),
            )
        )

        with get_connection(effective_db_path) as conn:
            # Load opcional de tickers B3
            s1 = _now()
            loaded_tickers = load_b3_tickers(
                conn,
                b3_tickers_dir,
                glob_pattern=settings.b3_tickers_glob,
            )
            step_reports.append(
                StepReport(
                    name="load_b3_tickers",
                    status="success" if loaded_tickers > 0 else "warning",
                    message=(f"{loaded_tickers} linhas carregadas em b3_tickers"),
                    metrics={
                        "rows_loaded": loaded_tickers,
                        "table": "b3_tickers",
                    },
                    started_at=s1,
                    finished_at=_now(),
                )
            )

            # Load financeiro
            s2 = _now()
            loaded_total = 0
            per_source_year: dict[str, int] = {}
            for year in years:
                for source in ("itr", "dfp"):
                    results = load_source_year(conn, source, year, effective_data_dir / "raw")
                    subtotal = sum(results.values())
                    per_source_year[f"{source}_{year}"] = subtotal
                    loaded_total += subtotal
            step_reports.append(
                StepReport(
                    name="load_financial",
                    status="success" if loaded_total > 0 else "warning",
                    message=(
                        f"{loaded_total} linhas carregadas em raw_*"
                        if loaded_total > 0
                        else "Nenhuma linha carregada (rode download primeiro)"
                    ),
                    metrics=per_source_year,
                    started_at=s2,
                    finished_at=_now(),
                )
            )

            # Normalize
            s3 = _now()
            normalized = normalize_all(conn)
            step_reports.append(
                StepReport(
                    name="normalize_financial",
                    status="success" if normalized else "warning",
                    message=(
                        f"{sum(normalized.values())} linhas normalizadas"
                        if normalized
                        else "Nenhuma tabela raw_* encontrada para normalizar"
                    ),
                    metrics=normalized,
                    started_at=s3,
                    finished_at=_now(),
                )
            )

            # Indicators
            s4 = _now()
            indicators_rows = calculate_all(conn, cnpj=cnpj)
            step_reports.append(
                StepReport(
                    name="indicators",
                    status="success" if indicators_rows > 0 else "warning",
                    message=(
                        f"{indicators_rows} registros gravados em indicators"
                        if indicators_rows > 0
                        else "Nenhum indicador calculado (verifique normalize/dados)"
                    ),
                    metrics={"rows": indicators_rows, "cnpj": cnpj},
                    started_at=s4,
                    finished_at=_now(),
                )
            )

            # Download cadastral
            s5 = _now()
            meta_path, cad_csv_path = download_info_cad(
                settings.cad_meta_url,
                settings.cad_csv_url,
                effective_data_dir / "raw" / "cad",
                force=force_download,
            )
            step_reports.append(
                StepReport(
                    name="download_info_cad",
                    status="success",
                    message="Arquivos cadastrais OK",
                    metrics={"meta": str(meta_path), "csv": str(cad_csv_path)},
                    started_at=s5,
                    finished_at=_now(),
                )
            )

            # Load cadastral
            s6 = _now()
            if cad_csv_path is None or not cad_csv_path.exists():
                raise RuntimeError("Arquivo cad_cia_aberta.csv não encontrado após download")
            inserted = load_info_cad(conn, cad_csv_path)
            step_reports.append(
                StepReport(
                    name="load_info_cad",
                    status="success" if inserted > 0 else "warning",
                    message=(
                        f"{inserted} linhas inseridas em cad_cia_aberta_raw"
                        if inserted > 0
                        else "cad_cia_aberta_raw ficou vazia (arquivo vazio?)"
                    ),
                    metrics={"rows": inserted},
                    started_at=s6,
                    finished_at=_now(),
                )
            )

            # Classify cadastral
            s7 = _now()
            counts = classify_info_cad(conn)
            step_reports.append(
                StepReport(
                    name="classify_info_cad",
                    status="success" if (counts.get("total", 0) or 0) > 0 else "warning",
                    message=(
                        f"{counts.get('total', 0)} CNPJs classificados"
                        if (counts.get("total", 0) or 0) > 0
                        else "Nenhuma classificação gerada"
                    ),
                    metrics=counts,
                    started_at=s7,
                    finished_at=_now(),
                )
            )

        # Status global: error se algum step error; warning se algum warning; caso contrário success
        statuses = [s.status for s in step_reports]
        if "error" in statuses:
            overall = "error"
        elif "warning" in statuses:
            overall = "warning"
        else:
            overall = "success"

        finished_at = _now()
        return PipelineReport(
            name="full",
            status=overall,
            steps=step_reports,
            started_at=started_at,
            finished_at=finished_at,
        )

    except Exception as exc:
        finished_at = _now()
        report = PipelineReport(
            name="full",
            status="error",
            steps=step_reports,
            started_at=started_at,
            finished_at=finished_at,
        )
        logger.exception("Falha no pipeline full")
        raise PipelineExecutionError(
            "Falha ao executar pipeline full",
            report=report,
            cause=exc,
        ) from exc
