# Download de Informações Cadastrais CVM handler
from pathlib import Path

from cvmdata.cli.models import DownloadInfoCadInput, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.downloader import download_info_cad


def handle(input: DownloadInfoCadInput) -> Outcome[dict]:
    """Baixa arquivos de informações cadastrais CVM (meta + CSV).
    
    Returns paths of downloaded meta and CSV files.
    """
    settings.cad_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        meta_path, csv_path = download_info_cad(
            settings.cad_meta_url,
            settings.cad_csv_url,
            settings.cad_dir,
            force=input.force,
        )
        
        # Return metadata about downloaded files
        payload = {
            "meta_file": meta_path.name,
            "csv_file": csv_path.name,
            "csv_size_bytes": csv_path.stat().st_size,
        }
        
        message = f"{csv_path.name} ({payload['csv_size_bytes']:,} bytes)"
        return Outcome.success(message=message, payload=payload)
        
    except FileNotFoundError as exc:
        return Outcome.error(f"Dados de informações cadastrais não encontrados no servidor CVM: {exc}")
    except Exception as exc:
        return Outcome.error(f"Falha no download das informações cadastrais: {exc}")
