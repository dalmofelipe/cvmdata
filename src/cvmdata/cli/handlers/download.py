# Download handler implementation
from cvmdata.cli.models import DownloadInput, Outcome
from cvmdata.ingestion.downloader import download_source_year
from cvmdata.config import settings


def handle(input: DownloadInput) -> Outcome[dict[str, int]]:
    """Download ITR and DFP ZIPs from CVM.
    
    Args:
        input: DownloadInput with years, force flag, verbose flag.
    
    Returns:
        Outcome with file count per source_year, or error/warning.
    """
    files_by_source_year = {}
    
    for year in input.years:
        for source in ("itr", "dfp"):
            url_tmpl = getattr(settings, f"{source}_url_template")
            try:
                files = download_source_year(
                    source, year, url_tmpl, settings.raw_dir, force=input.force
                )
                files_by_source_year[f"{source}_{year}"] = len(files)
            except FileNotFoundError:
                return Outcome.error(f"Data for {source}/{year} not found on CVM server")
            except Exception as exc:
                return Outcome.error(f"Download failed: {exc}")
    
    if not files_by_source_year:
        return Outcome.warning("No files downloaded")
    
    total = sum(files_by_source_year.values())
    return Outcome.success(
        message=f"Downloaded {total} CSVs",
        payload=files_by_source_year
    )

