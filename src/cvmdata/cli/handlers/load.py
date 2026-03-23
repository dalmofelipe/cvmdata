# Load handler implementation
from cvmdata.cli.models import LoadInput, Outcome
from cvmdata.ingestion.loader import load_source_year
from cvmdata.ingestion.db import get_connection
from cvmdata.config import settings


def handle(input: LoadInput) -> Outcome[dict[str, int]]:
    """Load extracted CSVs into DuckDB.
    
    Args:
        input: LoadInput with years and verbose flag.
    
    Returns:
        Outcome with row count per source_year, or warning/error.
    """
    results = {}
    
    with get_connection(settings.db_path) as conn:
        for year in input.years:
            for source in ("itr", "dfp"):
                try:
                    count = load_source_year(conn, source, year, settings.raw_dir)
                    if count:
                        results[f"{source}_{year}"] = count
                except Exception as exc:
                    return Outcome.error(f"Load {source}/{year} failed: {exc}")
    
    if not results:
        return Outcome.warning("No CSV files found — run 'download' first")
    
    total = sum(results.values())
    return Outcome.success(
        message=f"Loaded {total:,} rows in {len(results)} tables",
        payload=results
    )

