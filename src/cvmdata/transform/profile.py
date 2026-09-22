"""Resolução de perfil por CNPJ: cadastro → assinatura estrutural → default.

Cadeia de precedência:
  1. ``company_classification.profile_id`` (alta confiança quando o setor está
     mapeado em ``setor_profile_map``).
  2. Assinatura estrutural — apenas quando o CNPJ está totalmente ausente de
     ``cad_cia_aberta_raw`` (não confundir com ``SIT != 'ATIVO'``, que já cai
     em default sem assinatura) e de ``company_classification``. Dispara de
     acordo com ``SIGNATURE_RULES``.
  3. Fallback: ``default``.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb


def _existing_tables(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
    }


@dataclass(frozen=True)
class SignatureRule:
    profile_id: str
    cd_conta: str
    ds_conta_normalized: str
    description: str = ""


SIGNATURE_RULES: list[SignatureRule] = [
    SignatureRule(
        profile_id="banking",
        cd_conta="1.01",
        ds_conta_normalized="caixa e equivalentes de caixa",
        description="BPA 1.01 agregado, sem subdivisão 1.01.01 (design 3.3).",
    ),
]


def find_profiles_missing_info_cad(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> dict[str, str]:
    """Busca profile_id via assinatura estrutural, para CNPJs ausentes
    do cadastro e de ``company_classification``.
    """
    tables = _existing_tables(conn)
    if "raw_bpa_clean" not in tables:
        return {}
    not_in_info_cad = (
        "AND CNPJ_CIA NOT IN (SELECT CNPJ_CIA FROM cad_cia_aberta_raw)"
        if "cad_cia_aberta_raw" in tables
        else ""
    )
    not_in_classification = (
        "AND CNPJ_CIA NOT IN (SELECT cnpj_cia FROM company_classification)"
        if "company_classification" in tables
        else ""
    )
    filter_clause = "AND CNPJ_CIA = ?" if cnpj else ""
    result: dict[str, str] = {}
    for rule in SIGNATURE_RULES:
        params: list[object] = [rule.cd_conta, rule.ds_conta_normalized]
        if cnpj:
            params.append(cnpj)
        rows = conn.execute(
            f"""
            SELECT DISTINCT CNPJ_CIA
            FROM raw_bpa_clean
            WHERE CD_CONTA = ?
              AND lower(strip_accents(trim(DS_CONTA))) = ?
              {not_in_info_cad}
              {not_in_classification}
              {filter_clause}
            """,
            params,
        ).fetchall()
        for (found_cnpj,) in rows:
            result.setdefault(found_cnpj, rule.profile_id)
    return result


def fetch_profiles_from_classification(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> dict[str, str]:
    """Batch: perfil por CNPJ persistido em ``company_classification``.

    Returns:
        ``profiles_in_classification``: dict ``cnpj -> profile_id`` trazendo
        apenas CNPJs com classificação persistida.

    Tabela ``company_classification`` ausente (pipeline só de indicadores) →
    dict vazio: o cálculo resolve tudo como ``default``.
    """
    profiles: dict[str, str] = {}

    tables = _existing_tables(conn)
    if "company_classification" in tables:
        rows = conn.execute(
            "SELECT cnpj_cia, profile_id FROM company_classification"
        ).fetchall()
        profiles = {cnpj_cia: profile_id for cnpj_cia, profile_id in rows}

    if cnpj is not None:
        profiles = {k: v for k, v in profiles.items() if k == cnpj}

    return profiles