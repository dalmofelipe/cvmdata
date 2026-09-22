"""Testes de integração do módulo cadastral: load_cadastro e classify_cadastro."""

from __future__ import annotations

import pytest

from cvmdata.ingestion.database import init_info_cad_schema
from cvmdata.ingestion.loader import load_info_cad
from cvmdata.transform.info_cad import (
    EVENT_AMBIGUOUS,
    EVENT_EMPTY,
    EVENT_MISSING_FROM_CADASTRO,
    EVENT_UNMAPPED,
    FALLBACK_PROFILE,
    STRUCTURAL_CONFIDENCE,
    classify_info_cad,
)
from tests.support import make_cad_csv, seed_classification_rows, setup_classify_schema

pytestmark = pytest.mark.integration


def test_load_cadastro_returns_row_count(tmp_path, db):
    csv_path = make_cad_csv(
        tmp_path / "cad.csv",
        [
            {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
            {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "CANCELADA", "SETOR_ATIV": "Alimentos"},
            {"CNPJ_CIA": "33.333.333/0001-33", "SIT": "ATIVO", "SETOR_ATIV": ""},
        ],
    )
    inserted = load_info_cad(db, csv_path)
    assert inserted == 3


def test_load_cadastro_table_contains_all_rows(tmp_path, db):
    csv_path = make_cad_csv(
        tmp_path / "cad.csv",
        [
            {"CNPJ_CIA": "11.111.111/0001-11"},
            {"CNPJ_CIA": "22.222.222/0001-22"},
        ],
    )
    load_info_cad(db, csv_path)
    count = db.execute("SELECT COUNT(*) FROM cad_cia_aberta_raw").fetchone()[0]
    assert count == 2


def test_load_cadastro_idempotent(tmp_path, db):
    rows = [
        {"CNPJ_CIA": "11.111.111/0001-11"},
        {"CNPJ_CIA": "22.222.222/0001-22"},
    ]
    csv_path = make_cad_csv(tmp_path / "cad.csv", rows)
    load_info_cad(db, csv_path)
    load_info_cad(db, csv_path)
    count = db.execute("SELECT COUNT(*) FROM cad_cia_aberta_raw").fetchone()[0]
    assert count == 2


def test_load_cadastro_has_loaded_at_column(tmp_path, db):
    csv_path = make_cad_csv(tmp_path / "cad.csv", [{"CNPJ_CIA": "11.111.111/0001-11"}])
    load_info_cad(db, csv_path)
    count = db.execute(
        "SELECT COUNT(*) FROM cad_cia_aberta_raw WHERE loaded_at IS NOT NULL"
    ).fetchone()[0]
    assert count == 1


def test_load_cadastro_preserves_cancelled_rows(tmp_path, db):
    csv_path = make_cad_csv(
        tmp_path / "cad.csv",
        [
            {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO"},
            {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "CANCELADA"},
        ],
    )
    load_info_cad(db, csv_path)
    cancelled = db.execute(
        "SELECT COUNT(*) FROM cad_cia_aberta_raw WHERE SIT = 'CANCELADA'"
    ).fetchone()[0]
    assert cancelled == 1


def test_classify_raises_without_raw_table(db):
    init_info_cad_schema(db)
    with pytest.raises(RuntimeError, match="cad_cia_aberta_raw"):
        classify_info_cad(db)

@pytest.mark.parametrize(
    "cnpj, setor_ativ",
    [
        ("11.000.000/0001-11", "Bancos"),
        ("22.000.000/0001-22", "Arrendamento Mercantil"),
        ("23.000.000/0001-23", "Intermediacao Financeira"),
    ],
)
def test_classify_banking_high_confidence(db, cnpj, setor_ativ):
    seed_classification_rows(db, [{"CNPJ_CIA": cnpj, "SIT": "ATIVO", "SETOR_ATIV": setor_ativ}])

    counts = classify_info_cad(db)

    assert counts["high"] == 1
    assert counts["low"] == 0
    row = db.execute("SELECT profile_id, confidence FROM company_classification").fetchone()
    assert row[0] == "banking"
    assert row[1] == "high"


@pytest.mark.parametrize(
    "cnpj, setor_ativ, event_type, rule_substr",
    [
        ("33.000.000/0001-33", "Alimentos", EVENT_UNMAPPED, "unmapped_setor"),
        ("44.000.000/0001-44", "", EVENT_EMPTY, "empty_setor"),
    ],
)
def test_classify_low_confidence_and_curation_event(db, cnpj, setor_ativ, event_type, rule_substr):
    seed_classification_rows(db, [{"CNPJ_CIA": cnpj, "SIT": "ATIVO", "SETOR_ATIV": setor_ativ}])

    counts = classify_info_cad(db)

    assert counts["low"] == 1
    row = db.execute(
        "SELECT profile_id, confidence, rule_applied FROM company_classification"
    ).fetchone()
    assert row[0] == FALLBACK_PROFILE
    assert row[1] == "low"
    assert rule_substr in row[2]

    event = db.execute(
        "SELECT event_type FROM classification_curation_events WHERE cnpj_cia = ?",
        [cnpj],
    ).fetchone()
    assert event is not None
    assert event[0] == event_type


def test_classify_ambiguous_setor_low_confidence(db):
    seed_classification_rows(
        db,
        [
            {"CNPJ_CIA": "55.000.000/0001-55", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
            {"CNPJ_CIA": "55.000.000/0001-55", "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"},
        ],
    )

    counts = classify_info_cad(db)

    assert counts["low"] == 1
    row = db.execute(
        "SELECT profile_id, confidence FROM company_classification"
        " WHERE cnpj_cia = '55.000.000/0001-55'"
    ).fetchone()
    assert row[0] == FALLBACK_PROFILE
    assert row[1] == "low"


def test_classify_ambiguous_creates_curation_event(db):
    seed_classification_rows(
        db,
        [
            {"CNPJ_CIA": "55.000.000/0001-55", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
            {"CNPJ_CIA": "55.000.000/0001-55", "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"},
        ],
    )
    classify_info_cad(db)

    event = db.execute(
        "SELECT event_type FROM classification_curation_events"
        " WHERE cnpj_cia = '55.000.000/0001-55'"
    ).fetchone()
    assert event is not None
    assert event[0] == EVENT_AMBIGUOUS


def test_classify_cancelled_only_not_classified(db):
    seed_classification_rows(
        db, [{"CNPJ_CIA": "66.000.000/0001-66", "SIT": "CANCELADA", "SETOR_ATIV": "Bancos"}]
    )

    counts = classify_info_cad(db)

    assert counts["total"] == 0
    assert db.execute("SELECT COUNT(*) FROM company_classification").fetchone()[0] == 0


def test_classify_different_tp_merc_same_setor_is_high(db):
    seed_classification_rows(
        db,
        [
            {
                "CNPJ_CIA": "77.000.000/0001-77",
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "TP_MERC": "BOLSA",
                "DT_INI_SIT": "2020-01-01",
            },
            {
                "CNPJ_CIA": "77.000.000/0001-77",
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "TP_MERC": "BALCAO ORGANIZADO",
                "DT_INI_SIT": "2021-01-01",
            },
        ],
    )

    counts = classify_info_cad(db)

    assert counts["high"] == 1
    assert counts["low"] == 0
    count = db.execute(
        "SELECT COUNT(*) FROM company_classification WHERE cnpj_cia = '77.000.000/0001-77'"
    ).fetchone()[0]
    assert count == 1


def test_classify_picks_most_recent_dt_ini_sit_for_descriptive_fields(db):
    seed_classification_rows(
        db,
        [
            {
                "CNPJ_CIA": "88.000.000/0001-88",
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "DENOM_SOCIAL": "BANCO ANTIGO",
                "CD_CVM": "100",
                "DT_INI_SIT": "2010-01-01",
            },
            {
                "CNPJ_CIA": "88.000.000/0001-88",
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "DENOM_SOCIAL": "BANCO ATUAL",
                "CD_CVM": "100",
                "DT_INI_SIT": "2023-01-01",
            },
        ],
    )
    classify_info_cad(db)

    row = db.execute(
        "SELECT denom_social FROM company_classification WHERE cnpj_cia = '88.000.000/0001-88'"
    ).fetchone()
    assert row[0] == "BANCO ATUAL"


def test_classify_idempotent(db):
    seed_classification_rows(
        db,
        [
            {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
            {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"},
        ],
    )

    c1 = classify_info_cad(db)
    c2 = classify_info_cad(db)

    assert c1 == c2
    assert db.execute("SELECT COUNT(*) FROM company_classification").fetchone()[0] == 2


def test_classify_curation_events_not_duplicated_on_rerun(db):
    seed_classification_rows(db, [
        {"CNPJ_CIA": "33.333.333/0001-33", "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"}
    ])

    classify_info_cad(db)
    classify_info_cad(db)

    count = db.execute(
        "SELECT COUNT(*) FROM classification_curation_events WHERE cnpj_cia = '33.333.333/0001-33'"
    ).fetchone()[0]
    assert count == 1


def test_classify_returns_correct_counts(db):
    seed_classification_rows(
        db,
        [
            {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
            {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "ATIVO", "SETOR_ATIV": ""},
            {"CNPJ_CIA": "33.333.333/0001-33", "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"},
            {"CNPJ_CIA": "44.444.444/0001-44", "SIT": "CANCELADA", "SETOR_ATIV": "Bancos"},
        ],
    )

    counts = classify_info_cad(db)

    assert counts["total"] == 3
    assert counts["high"] == 1
    assert counts["low"] == 2


# ── Classificação estrutural (CNPJ ausente do cadastro, pós-normalize) ────────


def _seed_structural_bpa(db, cnpj: str) -> None:
    """Cria raw_bpa_clean mínimo com assinatura bancária para o CNPJ."""
    db.execute(
        """
        CREATE TABLE raw_bpa_clean (
            CNPJ_CIA VARCHAR, CD_CONTA VARCHAR, DS_CONTA VARCHAR,
            CD_CVM VARCHAR, DENOM_CIA VARCHAR
        )
        """
    )
    db.execute(
        """
        INSERT INTO raw_bpa_clean VALUES (?, '1.01', 'Caixa e Equivalentes de Caixa',
                                          '00123', 'BANCO INTER TESTE')
        """,
        [cnpj],
    )


def test_classify_structural_persists_when_absent_from_cadastro(db):
    """CNPJ com demonstrativos (raw_bpa_clean) mas ausente do cadastro → classificado
    estruturalmente como banking/medium, persistido em company_classification."""
    setup_classify_schema(db)
    # Media cadastral existente, mas sem o CNPJ de interesse
    seed_classification_rows(db, [{"CNPJ_CIA": "99.999.999/0001-99", "SIT": "ATIVO"}])
    _seed_structural_bpa(db, "42.737.954/0001-21")

    counts = classify_info_cad(db)

    assert counts["structural"] == 1
    assert counts["total"] == 2

    row = db.execute(
        "SELECT profile_id, confidence, cd_cvm, denom_social, denom_comerc, setor_ativ"
        " FROM company_classification WHERE cnpj_cia = ?",
        ["42.737.954/0001-21"],
    ).fetchone()
    assert row[0] == "banking"
    assert row[1] == STRUCTURAL_CONFIDENCE
    # Enriquecimento descritivo a partir de raw_bpa_clean
    assert row[2] == "00123"
    assert row[3] == "BANCO INTER TESTE"
    assert row[4] == "BANCO INTER TESTE"
    assert row[5] is None

    event = db.execute(
        "SELECT event_type FROM classification_curation_events WHERE cnpj_cia = ?",
        ["42.737.954/0001-21"],
    ).fetchone()
    assert event is not None
    assert event[0] == EVENT_MISSING_FROM_CADASTRO


def test_classify_structural_skips_cnpjs_in_cadastro(db):
    """CNPJ presente em cad_cia_aberta_raw (mesmo que não-classificável,
    ex.: CANCELADA) NÃO recebe classificação estrutural."""
    seed_classification_rows(
        db, [{"CNPJ_CIA": "42.737.954/0001-21", "SIT": "CANCELADA", "SETOR_ATIV": ""}]
    )
    _seed_structural_bpa(db, "42.737.954/0001-21")

    counts = classify_info_cad(db)

    assert counts["structural"] == 0
    assert db.execute("SELECT COUNT(*) FROM company_classification").fetchone()[0] == 0


def test_classify_structural_skips_already_classified(db):
    """CNPJ já persistido em company_classification não é re-classificado
    estruturalmente — a classificação existente tem precedência."""
    setup_classify_schema(db)
    seed_classification_rows(db, [{"CNPJ_CIA": "99.999.999/0001-99", "SIT": "ATIVO"}])
    db.execute(
        "INSERT INTO company_classification"
        " (cnpj_cia, profile_id, confidence, rule_applied, updated_at)"
        " VALUES (?, 'default', 'low', 'unmapped_setor:x:fallback', current_timestamp)",
        ["42.737.954/0001-21"],
    )
    _seed_structural_bpa(db, "42.737.954/0001-21")

    counts = classify_info_cad(db)

    assert counts["structural"] == 0
    row = db.execute(
        "SELECT profile_id, confidence FROM company_classification WHERE cnpj_cia = ?",
        ["42.737.954/0001-21"],
    ).fetchone()
    assert row == ("default", "low")


def test_classify_structural_idempotent(db):
    """Rerun não duplica linhas estruturais em company_classification.

    Primeira run classifica estruturalmente (structural=1); a segunda encontra
    o CNPJ já persistido em company_classification e não re-classifica
    (structural=0), sem duplicar a linha."""
    setup_classify_schema(db)
    seed_classification_rows(db, [{"CNPJ_CIA": "99.999.999/0001-99", "SIT": "ATIVO"}])
    _seed_structural_bpa(db, "42.737.954/0001-21")

    c1 = classify_info_cad(db)
    c2 = classify_info_cad(db)

    assert c1["structural"] == 1
    assert c2["structural"] == 0
    count = db.execute(
        "SELECT COUNT(*) FROM company_classification WHERE cnpj_cia = ?",
        ["42.737.954/0001-21"],
    ).fetchone()[0]
    assert count == 1
