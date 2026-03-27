# Load cadastro CVM handler
from cvmdata.cli.models import LoadCadInput, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.ingestion.loader import load_cadastro


def handle(input: LoadCadInput) -> Outcome[int]:
    """Carrega cad_cia_aberta.csv para o DuckDB.
    
    Returns the number of rows inserted.
    """
    csv_path = settings.cad_dir / "cad_cia_aberta.csv"
    
    if not csv_path.exists():
        return Outcome.warning(
            f"Arquivo cadastral não encontrado — rode 'download-cad' primeiro"
        )
    
    try:
        with get_connection(settings.db_path) as conn:
            inserted = load_cadastro(conn, csv_path)
        
        message = f"{inserted:,} linhas em cad_cia_aberta_raw"
        return Outcome.success(message=message, payload=inserted)
        
    except Exception as exc:
        return Outcome.error(f"Falha no load do cadastro: {exc}")
