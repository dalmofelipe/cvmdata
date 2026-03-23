# Indicators handler implementation
from cvmdata.cli.models import IndicatorsInput, Outcome
from cvmdata.transform.indicators import calculate_all
from cvmdata.ingestion.db import get_connection
from cvmdata.config import settings


def handle(input: IndicatorsInput) -> Outcome[int]:
    """Calculate fundamental indicators.
    
    Args:
        input: IndicatorsInput with optional CNPJ filter and verbose flag.
    
    Returns:
        Outcome with total indicator count, or warning/error.
    """
    with get_connection(settings.db_path) as conn:
        try:
            total = calculate_all(conn, cnpj=input.cnpj)
        except Exception as exc:
            return Outcome.error(f"Indicator calculation failed: {exc}")
    
    if total == 0:
        return Outcome.warning("No indicators calculated — run 'normalize' first")
    
    return Outcome.success(
        message=f"Calculated {total:,} indicators",
        payload=total
    )

