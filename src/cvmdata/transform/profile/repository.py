"""Persistência de ``company_classification``.

A tabela é do subdomínio classificação, e portanto mora aqui: ``profile`` é quem
diz o que um perfil significa, ``info_cad`` é quem alimenta a tabela. Por isso o
``DELETE`` + ``INSERT`` de reconstrução também fica aqui, e não no consumidor.
"""

from __future__ import annotations

import logging

import duckdb

from cvmdata.ingestion.tables import TB_COMPANY_CLASSIFICATION

logger = logging.getLogger(__name__)


def table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    """Se ``table`` existe no schema ``main``."""
    return table in existing_tables(conn)


def existing_tables(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Nomes de todas as tabelas do schema ``main``."""
    return {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
    }


def rebuild(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    params: list[object],
) -> None:
    """Reconstrói ``company_classification`` inteira, em transação.

    A reconstrução — e não um ``INSERT OR REPLACE`` — é o que garante que a
    classificação não carrega linha obsoleta: um CNPJ que saiu do universo no
    ano corrente precisa sumir.

    Args:
        conn: Conexão DuckDB.
        sql: Statement ``INSERT`` de classificação já renderizado.
        params: Params do ``sql``, na mesma ordem.
    """
    conn.execute("BEGIN")
    try:
        conn.execute(f"DELETE FROM {TB_COMPANY_CLASSIFICATION}")
        conn.execute(sql, params)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def fetch_profiles(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> dict[str, str]:
    """Batch: perfil por CNPJ persistido em ``company_classification``.

    Args:
        conn: Conexão DuckDB.
        cnpj: Se informado, filtra o resultado para um CNPJ.

    Returns:
        ``profiles``: dict ``cnpj -> profile_id`` trazendo apenas CNPJs com
        classificação persistida.

    Tabela ``company_classification`` ausente (pipeline só de indicadores) →
    dict vazio: o cálculo resolve tudo como ``default``.
    """
    profiles: dict[str, str] = {}

    if table_exists(conn, TB_COMPANY_CLASSIFICATION):
        rows = conn.execute(
            f"SELECT cnpj_cia, profile_id FROM {TB_COMPANY_CLASSIFICATION}"
        ).fetchall()
        profiles = {cnpj_cia: profile_id for cnpj_cia, profile_id in rows}

    if cnpj is not None:
        profiles = {k: v for k, v in profiles.items() if k == cnpj}

    return profiles


def count_by_profile_and_rule(
    conn: duckdb.DuckDBPyConnection,
) -> tuple[dict[str, int], dict[str, int]]:
    """Conta as linhas persistidas, agrupadas por perfil e por ``rule_applied``."""
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