from cvmdata.cli.models import (
    IndicatorsInput,
    IndicatorsResult,
    InfoCadInput,
    InfoCadResult,
    Outcome,
    Paged,
)
from cvmdata.config import settings
from cvmdata.ingestion import db


def indicators(input: IndicatorsInput) -> Outcome[list[IndicatorsResult]]:
    """Consulta indicadores calculados para uma empresa (CNPJ obrigatório)."""
    with db.get_connection(settings.db_path) as conn:
        try:
            params: list[object] = [input.cnpj]
            year_clause = ""
            if input.year is not None:
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


def info_cad(input: InfoCadInput) -> Outcome[list[InfoCadResult]]:
    """Consulta dados cadastrais e classificação setorial para uma empresa (CNPJ opcional)."""
    with db.get_connection(settings.db_path) as conn:
        try:
            if input.cnpj is None:
                # Summary: last N classifications (paged)
                limit = input.page_size
                page = input.page or 1
                offset = (page - 1) * limit

                rows = conn.execute(
                    """
                    SELECT cnpj_cia, denom_social, setor_ativ, profile_id, confidence, updated_at
                    FROM   company_classification
                    ORDER BY updated_at DESC NULLS LAST, cnpj_cia ASC
                    LIMIT  ? OFFSET ?
                    """,
                    [limit, offset],
                ).fetchall()
            else:
                # Detail: full record for specific CNPJ
                rows = conn.execute(
                    """
                    SELECT cnpj_cia, cd_cvm, denom_social, denom_comerc,
                           setor_ativ, profile_id, confidence, rule_applied, updated_at
                    FROM   company_classification
                    WHERE  cnpj_cia = ?
                    """,
                    [input.cnpj],
                ).fetchall()

        except Exception as exc:
            return Outcome.error(f"Falha na consulta de cadastro: {exc}")

    if not rows:
        if input.cnpj:
            return Outcome.warning(f"Nenhuma classificação encontrada para CNPJ {input.cnpj!r}")
        return Outcome.warning(
            f"Nenhuma classificação encontrada (página {input.page}) — rode 'classify-cad' primeiro"
        )

    results: list[InfoCadResult] = []

    if input.cnpj is None:
        # Summary mode: 6 columns
        for row in rows:
            results.append(
                InfoCadResult(
                    cnpj_cia=row[0],
                    denom_social=row[1],
                    setor_ativ=row[2],
                    profile_id=row[3],
                    confidence=row[4],
                    updated_at=str(row[5]) if row[5] is not None else None,
                )
            )
    else:
        # Detail mode: 9 columns
        for row in rows:
            results.append(
                InfoCadResult(
                    cnpj_cia=row[0],
                    cd_cvm=row[1],
                    denom_social=row[2],
                    denom_comerc=row[3],
                    setor_ativ=row[4],
                    profile_id=row[5],
                    confidence=row[6],
                    rule_applied=row[7],
                    updated_at=str(row[8]) if row[8] is not None else None,
                )
            )

    if input.cnpj is None:
        return Outcome.success(payload=Paged(items=results, page=input.page, page_size=limit))

    return Outcome.success(payload=results)
