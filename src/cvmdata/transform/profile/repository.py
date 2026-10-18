from __future__ import annotations

import duckdb

from cvmdata.ingestion.tables import TB_COMPANY_CLASSIFICATION
from cvmdata.utils.database import table_exists


def fetch_profiles(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> dict[str, str]:
    """Batch: perfil por CNPJ persistido em ``company_classification``.

    ### Args
        conn: Conexão DuckDB.
        cnpj: Se informado, filtra o resultado para um CNPJ.

    ### Returns
        profiles: ``dict[str, str]`` com o mapeamento ``cnpj_cia -> profile_id``.

    ### Example
    
        >>> fetch_profiles(conn)                    # doctest: +SKIP
        {'42.737.954/0001-21': 'banking', '33.000.167/0001-01': 'default'}
    """
    profiles: dict[str, str] = {}

    if table_exists(conn, TB_COMPANY_CLASSIFICATION):
        query = f"SELECT cnpj_cia, profile_id FROM {TB_COMPANY_CLASSIFICATION}"
        params: list[object] = []
        if cnpj is not None:
            query += " WHERE cnpj_cia = ?"
            params.append(cnpj)

        rows = conn.execute(query, params,).fetchall()
        profiles = {cnpj_cia: profile_id for cnpj_cia, profile_id in rows}

    return profiles


def count_by_profile_and_rule(
    conn: duckdb.DuckDBPyConnection,
) -> tuple[dict[str, int], dict[str, int]]:
    """Conta as linhas persistidas, agrupadas por ``profile_id`` e por ``rule_applied``."""
    rows = conn.execute(
        f"""
        SELECT profile_id, rule_applied, count(*) AS n
        FROM {TB_COMPANY_CLASSIFICATION}
        GROUP BY profile_id, rule_applied
        ORDER BY n DESC
        """
    ).fetchall()

    by_profile: dict[str, int] = {}
    by_rule: dict[str, int] = {}
    for profile_id, rule_applied, n in rows:
        by_profile[profile_id] = by_profile.get(profile_id, 0) + n
        by_rule[rule_applied] = by_rule.get(rule_applied, 0) + n
    return by_profile, by_rule