# Query handler implementation
from cvmdata.cli.models import Outcome, QueryInput, QueryResult
from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection


def handle(input: QueryInput) -> Outcome[list[QueryResult]]:
    """Consulta indicadores calculados para resumo ou detalhe."""
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
            return Outcome.error(f"Falha na consulta: {exc}")
    
    if not rows:
        if input.cnpj:
            return Outcome.warning(f"Nenhum indicador encontrado para CNPJ {input.cnpj!r}")
        return Outcome.warning("Nenhum indicador encontrado — rode 'indicators' primeiro")
    
    results: list[QueryResult] = []
    if input.cnpj is None:
        for row in rows:
            results.append(
                QueryResult(
                    cnpj_cia=row[0],
                    n_indicadores=row[1],
                    primeiro_periodo=str(row[2]) if row[2] is not None else None,
                    ultimo_periodo=str(row[3]) if row[3] is not None else None,
                )
            )
    else:
        for row in rows:
            results.append(
                QueryResult(
                    cnpj_cia=row[0],
                    dt_refer=str(row[1]) if row[1] is not None else None,
                    indicador=row[2],
                    valor=row[3],
                )
            )
    
    return Outcome.success(payload=results)

