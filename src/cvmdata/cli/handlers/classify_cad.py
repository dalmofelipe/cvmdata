# Classify cadastro CVM handler
from cvmdata.cli.models import ClassifyCadInput, ClassifyCadResult, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.transform.cadastro import classify_cadastro


def handle(input: ClassifyCadInput) -> Outcome[ClassifyCadResult]:
    """Classifica CNPJs ativos por setor e persiste em company_classification.
    
    Returns classification statistics (total, high, low).
    """
    try:
        with get_connection(settings.db_path) as conn:
            counts = classify_cadastro(conn)
    
    except RuntimeError as exc:
        # Typically: cad_cia_aberta_raw table not found or empty
        return Outcome.warning(str(exc))
    except Exception as exc:
        return Outcome.error(f"Falha na classificação de cadastro: {exc}")
    
    result = ClassifyCadResult(
        total=counts["total"],
        high=counts["high"],
        low=counts["low"],
    )
    
    message = f"{result.total:,} CNPJs classificados ({result.high:,} high, {result.low:,} low)"
    return Outcome.success(message=message, payload=result)
