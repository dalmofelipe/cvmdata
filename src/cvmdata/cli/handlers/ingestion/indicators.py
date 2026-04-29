# Indicators handler implementation
from cvmdata.cli.models import IndicatorsInput, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.transform.indicators import calculate_all


def handle(input: IndicatorsInput) -> Outcome[int]:
    """Calcula indicadores fundamentalistas."""
    with get_connection(settings.db_path) as conn:
        try:
            total = calculate_all(conn, cnpj=input.cnpj)
        except Exception as exc:
            return Outcome.error(f"Falha no cálculo de indicadores: {exc}")
    
    if total == 0:
        return Outcome.warning("Nenhum indicador calculado — rode 'normalize' primeiro")
    
    return Outcome.success(
        message=f"{total:,} indicadores gravados em indicators",
        payload=total
    )

