# Normalize handler implementation
from cvmdata.cli.models import NormalizeInput, Outcome
from cvmdata.transform.normalize import normalize_all
from cvmdata.ingestion.db import get_connection
from cvmdata.config import settings


def handle(input: NormalizeInput) -> Outcome[dict[str, int]]:
    """Normalize, deduplicate, and consolidate raw data.
    
    Args:
        input: NormalizeInput with verbose flag.
    
    Returns:
        Outcome with row counts per table, or warning/error.
    """
    with get_connection(settings.db_path) as conn:
        try:
            results = normalize_all(conn)
        except Exception as exc:
            return Outcome.error(f"Normalization failed: {exc}")
    
    if not results:
        return Outcome.warning("No raw_* tables found — run 'load' first")
    
    total = sum(results.values())
    return Outcome.success(
        message=f"Normalized {len(results)} tables, {total:,} rows total",
        payload=results
    )

