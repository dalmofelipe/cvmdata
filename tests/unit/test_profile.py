"""Testes da resolução estrutural de perfil (design seção 3.3/3.4)."""

import duckdb

from cvmdata.transform.profile import (
    SignatureRule,
    find_profiles_missing_info_cad,
)

CNPJ_BANCO = "00.000.000/0001-91"
CNPJ_IND = "33.000.167/0001-01"


def _seeded_signature(
    db: duckdb.DuckDBPyConnection,
    *,
    cnpj: str = CNPJ_BANCO,
    cd_conta: str = "1.01",
    ds_conta: str = "Caixa e Equivalentes de Caixa",
) -> None:
    """Cria raw_bpa_clean mínimo com uma linha de assinatura (ou genérica)."""
    db.execute(
        "CREATE TABLE raw_bpa_clean (CNPJ_CIA VARCHAR, CD_CONTA VARCHAR, DS_CONTA VARCHAR)"
    )
    db.execute(
        "INSERT INTO raw_bpa_clean VALUES (?, ?, ?)", [cnpj, cd_conta, ds_conta]
    )


def _seed_cad_cia_aberta(db: duckdb.DuckDBPyConnection, cnpj: str) -> None:
    db.execute("CREATE TABLE cad_cia_aberta_raw (CNPJ_CIA VARCHAR)")
    db.execute("INSERT INTO cad_cia_aberta_raw VALUES (?)", [cnpj])


def _seed_company_classification(db: duckdb.DuckDBPyConnection, cnpj: str) -> None:
    db.execute("CREATE TABLE company_classification (cnpj_cia VARCHAR, profile_id VARCHAR)")
    db.execute("INSERT INTO company_classification VALUES (?, ?)", [cnpj, "default"])


# ── Detecção estrutural por SQL (design 3.3/3.4) ──────────────────────────────


def test_detect_structural_profiles_finds_signature(db):
    """CNPJ com BPA 1.01 = 'Caixa e Equivalentes de Caixa', ausente do
    cadastro — deve ser detectado como banking."""
    _seeded_signature(db)

    result = find_profiles_missing_info_cad(db)

    assert result == {CNPJ_BANCO: "banking"}


def test_detect_structural_profiles_ignora_ja_classificado(db):
    """Mesma assinatura, mas CNPJ já presente em cad_cia_aberta_raw — não
    deve entrar no resultado (cadastro tem precedência sobre heurística
    estrutural)."""
    _seeded_signature(db)
    _seed_cad_cia_aberta(db, CNPJ_BANCO)

    result = find_profiles_missing_info_cad(db)

    assert result == {}


def test_detect_structural_profiles_ignora_ja_persistido(db):
    """Mesma assinatura, mas CNPJ já persistido em company_classification —
    deve ser ignorado (classificação tem precedência sobre heurística)."""
    _seeded_signature(db)
    _seed_company_classification(db, CNPJ_BANCO)

    result = find_profiles_missing_info_cad(db)

    assert result == {}


def test_detect_structural_profiles_generic_new_rule(db, monkeypatch):
    """Adiciona uma regra fictícia a STRUCTURAL_SIGNATURE_RULES (via
    monkeypatch) para confirmar que a função funciona para qualquer
    profile_id, não só 'banking' — valida o design genérico."""
    rule = SignatureRule(
        profile_id="insurance",
        cd_conta="9.99",
        ds_conta_normalized="ativos intangiveis",
    )
    monkeypatch.setattr(
        "cvmdata.transform.profile.SIGNATURE_RULES", [rule]
    )
    _seeded_signature(db, cnpj=CNPJ_IND, cd_conta="9.99", ds_conta="Ativos Intangíveis")

    result = find_profiles_missing_info_cad(db)

    assert result == {CNPJ_IND: "insurance"}