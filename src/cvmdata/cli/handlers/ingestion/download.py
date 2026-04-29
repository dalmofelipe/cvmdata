# Download handler implementation
from cvmdata.cli.models import DownloadInput, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.downloader import download_source_year


def handle(input: DownloadInput) -> Outcome[dict[str, int]]:
    """Baixa arquivos ITR e DFP da CVM por ano."""
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
                return Outcome.error(f"Dados de {source}/{year} não encontrados no servidor CVM")
            except Exception as exc:
                return Outcome.error(f"Falha no download: {exc}")
    
    if not files_by_source_year:
        return Outcome.warning("Nenhum arquivo encontrado para download")
    
    total = sum(files_by_source_year.values())
    if total == 0:
        return Outcome.warning("Nenhum CSV novo para baixar")

    return Outcome.success(
        message=f"{total} CSVs prontos",
        payload=files_by_source_year
    )

