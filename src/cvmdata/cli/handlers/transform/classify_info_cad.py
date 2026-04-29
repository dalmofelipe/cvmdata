# Classify informações cadastrais CVM handler
from cvmdata.cli.models import ClassifyInfoCadInput, ClassifyInfoCadResult, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.transform.info_cad import classify_info_cad


def handle(input: ClassifyInfoCadInput) -> Outcome[ClassifyInfoCadResult]:
    """Classifica CNPJs ativos por setor e persiste em company_classification.
    
    Returns classification statistics (total, high, low).
    """
    try:
        with get_connection(settings.db_path) as conn:
            counts = classify_info_cad(conn)
    
    except RuntimeError as exc:
        # Typically: cad_cia_aberta_raw table not found or empty
        return Outcome.warning(str(exc))
    except Exception as exc:
        return Outcome.error(f"Falha na classificação de cadastro: {exc}")
    
    result = ClassifyInfoCadResult(
        total=counts["total"],
        high=counts["high"],
        low=counts["low"],
    )
    
    message = f"{result.total:,} CNPJs classificados ({result.high:,} high, {result.low:,} low)"
    return Outcome.success(message=message, payload=result)
