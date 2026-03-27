# Normalize handler implementation
from cvmdata.cli.models import NormalizeInput, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.transform.normalize import normalize_all


def handle(input: NormalizeInput) -> Outcome[dict[str, int]]:
    """Normaliza, deduplica e consolida dados brutos."""
    with get_connection(settings.db_path) as conn:
        try:
            results = normalize_all(conn)
        except Exception as exc:
            return Outcome.error(f"Falha na normalização: {exc}")
    
    if not results:
        return Outcome.warning("Nenhuma tabela raw_* encontrada — rode 'load' primeiro")
    
    total = sum(results.values())
    return Outcome.success(
        message=f"{len(results)} tabela(s) normalizadas, {total:,} linhas totais",
        payload=results
    )

