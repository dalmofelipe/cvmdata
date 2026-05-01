# Indicators handler implementation (renomeado de query.py)
from cvmdata.cli.models import IndicatorsInput, IndicatorsResult, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection


def handle(input: IndicatorsInput) -> Outcome[list[IndicatorsResult]]:
    """Consulta indicadores calculados para uma empresa (CNPJ obrigatório)."""
    with get_connection(settings.db_path) as conn:
        try:
            params: list[object] = [input.cnpj]
            year_clause = ""
            if hasattr(input, "year") and input.year is not None:
                year_clause = " AND YEAR(dt_refer) = ?"
                params.append(input.year)

            rows = conn.execute(
                f"""SELECT cnpj_cia, dt_refer, indicador, valor
                   FROM indicators
                   WHERE cnpj_cia = ?{year_clause}
                   ORDER BY dt_refer, indicador""",
                params,
            ).fetchall()
        except Exception as exc:
            return Outcome.error(f"Falha na consulta: {exc}")

    if not rows:
        return Outcome.warning(
            f"Nenhum indicador encontrado para CNPJ {input.cnpj!r} "
            "— rode 'cvmdata pipeline run' primeiro"
        )

    results: list[IndicatorsResult] = []
    for row in rows:
        results.append(
            IndicatorsResult(
                cnpj_cia=row[0],
                dt_refer=str(row[1]) if row[1] is not None else None,
                indicador=row[2],
                valor=row[3],
            )
        )

    return Outcome.success(payload=results)
