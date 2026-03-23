# Query handler implementation
from cvmdata.cli.models import QueryInput, QueryResult, Outcome
from cvmdata.ingestion.db import get_connection
from cvmdata.config import settings


def handle(input: QueryInput) -> Outcome[list[QueryResult]]:
    """Query calculated indicators.
    
    Args:
        input: QueryInput with optional CNPJ and year filters.
    
    Returns:
        Outcome with list[QueryResult] rows, or warning/error.
    """
    with get_connection(settings.db_path) as conn:
        try:
            if input.cnpj is None:
                # Summary: top 10 companies with most indicators
                rows = conn.execute(
                    """SELECT cnpj_cia, COUNT(DISTINCT indicador) AS n_indicadores,
                              MIN(dt_refer) AS primeiro_periodo, MAX(dt_refer) AS ultimo_periodo
                       FROM indicators GROUP BY cnpj_cia
                       ORDER BY n_indicadores DESC LIMIT 10"""
                ).fetchall()
            else:
                # Detail: indicators for specific company
                params = [input.cnpj]
                year_clause = ""
                if input.year is not None:
                    year_clause = " AND YEAR(dt_refer) = ?"
                    params.append(input.year)
                
                rows = conn.execute(
                    f"""SELECT cnpj_cia, dt_refer, indicador, valor
                       FROM indicators
                       WHERE cnpj_cia = ?{year_clause}
                       ORDER BY dt_refer, indicador""",
                    params
                ).fetchall()
        except Exception as exc:
            return Outcome.error(f"Query failed: {exc}")
    
    if not rows:
        cnpj_str = f" for {input.cnpj}" if input.cnpj else ""
        return Outcome.warning(f"No indicators found{cnpj_str}")
    
    # Convert rows to QueryResult objects
    results = [QueryResult(*row) for row in rows]
    
    return Outcome.success(payload=results)

