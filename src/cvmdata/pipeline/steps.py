from datetime import datetime, timezone
from pathlib import Path

import duckdb

from cvmdata.config import settings
from cvmdata.ingestion.downloader import download_info_cad, download_source_year
from cvmdata.ingestion.loader import load_b3_tickers, load_info_cad, load_source_year
from cvmdata.pipeline.models import StepReport
from cvmdata.transform.indicators import calculate_all
from cvmdata.transform.info_cad import classify_info_cad
from cvmdata.transform.normalize import normalize_all


def _now() -> datetime:
    return datetime.now(timezone.utc)


def step_downloads_cvm(
    years: list[int], 
    force_download: bool, 
    effective_data_dir: Path
) -> StepReport:
    started = _now()
    downloaded_counts: dict[str, int] = {}
    for year in years:
        for source, url_template in (
                ("itr", settings.itr_url_template), 
                ("dfp", settings.dfp_url_template)
            ):
            extracted = download_source_year(
                source,
                year,
                url_template,
                effective_data_dir / "raw",
                force=force_download,
            )
            downloaded_counts[f"{source}_{year}"] = len(extracted)
    return StepReport(
        name="download_financial",
        status="success" if any(downloaded_counts.values()) else "warning",
        message=(
            "ZIPs processados e CSVs extraídos"
            if any(downloaded_counts.values())
            else "Nenhum CSV novo extraído (provável cache local)"
        ),
        metrics=downloaded_counts,
        started_at=started,
        finished_at=_now(),
    )


def step_download_info_cad(
    force_download: bool, 
    effective_data_dir: Path
) -> tuple[Path, StepReport]:
    started = _now()
    meta_path, cad_csv_path = download_info_cad(
        settings.cad_meta_url,
        settings.cad_csv_url,
        effective_data_dir / "raw" / "cad",
        force=force_download,
    )
    return cad_csv_path, StepReport(
        name="download_info_cad",
        status="success",
        message="Arquivos cadastrais OK",
        metrics={"meta": str(meta_path), "csv": str(cad_csv_path)},
        started_at=started,
        finished_at=_now(),
    )


def step_load_b3_tickers(
    conn: duckdb.DuckDBPyConnection, 
    b3_tickers_dir: Path
) -> StepReport:
    """  """
    started = _now()
    loaded_tickers = load_b3_tickers(
        conn,
        b3_tickers_dir,
        glob_pattern=settings.b3_tickers_glob,
    )
    return StepReport(
        name="load_b3_tickers",
        status="success" if loaded_tickers > 0 else "warning",
        message=(f"{loaded_tickers} linhas carregadas em b3_tickers"),
        metrics={
            "rows_loaded": loaded_tickers,
            "table": "b3_tickers",
        },
        started_at=started,
        finished_at=_now(),
    )


def step_load_cvm(
    conn: duckdb.DuckDBPyConnection, 
    years: list[int], 
    effective_data_dir: Path
) -> StepReport:
    """  """
    started = _now()
    loaded_total = 0
    per_source_year: dict[str, int] = {}
    for year in years:
        for source in ("itr", "dfp"):
            results = load_source_year(conn, source, year, effective_data_dir / "raw")
            subtotal = sum(results.values())
            per_source_year[f"{source}_{year}"] = subtotal
            loaded_total += subtotal
    return StepReport(
        name="load_financial",
        status="success" if loaded_total > 0 else "warning",
        message=(
            f"{loaded_total} linhas carregadas em raw_*"
            if loaded_total > 0
            else "Nenhuma linha carregada (rode download primeiro)"
        ),
        metrics=per_source_year,
        started_at=started,
        finished_at=_now(),
    )


def step_load_info_cad(
    conn: duckdb.DuckDBPyConnection,
    cad_csv_path: Path
) -> StepReport:
    """  """
    started = _now()
    if cad_csv_path is None or not cad_csv_path.exists():
        raise RuntimeError("Arquivo cad_cia_aberta.csv não encontrado após download")
    inserted = load_info_cad(conn, cad_csv_path)
    return StepReport(
        name="load_info_cad",
        status="success" if inserted > 0 else "warning",
        message=(
            f"{inserted} linhas inseridas em cad_cia_aberta_raw"
            if inserted > 0
            else "cad_cia_aberta_raw ficou vazia (arquivo vazio?)"
        ),
        metrics={"rows": inserted},
        started_at=started,
        finished_at=_now(),
    )


def step_classify_info_cad(
    conn: duckdb.DuckDBPyConnection
) -> StepReport:
    """  """
    started = _now()
    counts = classify_info_cad(conn)
    return StepReport(
        name="classify_info_cad",
        status="success" if (counts.get("total", 0) or 0) > 0 else "warning",
        message=(
            f"{counts.get('total', 0)} CNPJs classificados"
            if (counts.get("total", 0) or 0) > 0
            else "Nenhuma classificação gerada"
        ),
        metrics=counts,
        started_at=started,
        finished_at=_now(),
    )


def step_normalize_financial(
    conn: duckdb.DuckDBPyConnection
) -> StepReport:
    """  """
    started = _now()
    normalized = normalize_all(conn)
    return StepReport(
        name="normalize_financial",
        status="success" if normalized else "warning",
        message=(
            f"{sum(normalized.values())} linhas normalizadas"
            if normalized
            else "Nenhuma tabela raw_* encontrada para normalizar"
        ),
        metrics=normalized,
        started_at=started,
        finished_at=_now(),
    )


def step_calculate_indicators(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None
) -> StepReport:
    """  """
    started = _now()
    indicators_rows = calculate_all(conn, cnpj=cnpj)
    return StepReport(
        name="indicators",
        status="success" if indicators_rows > 0 else "warning",
        message=(
            f"{indicators_rows} registros gravados em indicators"
            if indicators_rows > 0
            else "Nenhum indicador calculado (verifique normalize/dados)"
        ),
        metrics={"rows": indicators_rows, "cnpj": cnpj},
        started_at=started,
        finished_at=_now(),
    )
