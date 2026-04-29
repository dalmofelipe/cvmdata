"""Testes do módulo cadastral: load_cadastro e classify_cadastro."""
from __future__ import annotations

from pathlib import Path

import pytest

from cvmdata.ingestion.db import init_info_cad_schema
from cvmdata.ingestion.loader import load_info_cad
from cvmdata.transform.info_cad import (
    EVENT_AMBIGUOUS,
    EVENT_EMPTY,
    EVENT_UNMAPPED,
    FALLBACK_PROFILE,
    classify_info_cad,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_CAD_HEADER = (
    "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;CD_CVM;"
    "SIT;DT_INI_SIT;TP_MERC;CATEG_REG;SETOR_ATIV;DT_INC"
)


def _make_cad_csv(path: Path, rows: list[dict]) -> Path:
    """Cria CSV cadastral mínimo no formato CVM (latin-1, ';')."""
    lines = [_CAD_HEADER]
    for r in rows:
        lines.append(
            f"{r.get('CNPJ_CIA', '00.000.000/0001-91')};"
            f"{r.get('DENOM_SOCIAL', 'CIA TESTE')};"
            f"{r.get('DENOM_COMERC', '')};"
            f"{r.get('CD_CVM', '001')};"
            f"{r.get('SIT', 'ATIVO')};"
            f"{r.get('DT_INI_SIT', '2020-01-01')};"
            f"{r.get('TP_MERC', 'BOLSA')};"
            f"{r.get('CATEG_REG', 'A')};"
            f"{r.get('SETOR_ATIV', '')};"
            f"{r.get('DT_INC', '2020-01-01')}"
        )
    path.write_bytes("\n".join(lines).encode("latin-1"))
    return path


def _setup_classify_schema(conn):
    """Cria cad_cia_aberta_raw + tabelas auxiliares + seed de perfis."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cad_cia_aberta_raw (
            CNPJ_CIA     VARCHAR,
            DENOM_SOCIAL VARCHAR,
            DENOM_COMERC VARCHAR,
            CD_CVM       VARCHAR,
            SIT          VARCHAR,
            DT_INI_SIT   VARCHAR,
            TP_MERC      VARCHAR,
            CATEG_REG    VARCHAR,
            SETOR_ATIV   VARCHAR,
            DT_INC       VARCHAR,
            loaded_at    TIMESTAMPTZ
        )
    """)
    init_info_cad_schema(conn)


def _insert_raw(conn, rows: list[dict]):
    for r in rows:
        conn.execute(
            """
            INSERT INTO cad_cia_aberta_raw
                (CNPJ_CIA, DENOM_SOCIAL, DENOM_COMERC, CD_CVM, SIT, DT_INI_SIT,
                 TP_MERC, CATEG_REG, SETOR_ATIV, DT_INC, loaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            [
                r.get("CNPJ_CIA", "00.000.000/0001-91"),
                r.get("DENOM_SOCIAL", "CIA TESTE"),
                r.get("DENOM_COMERC", ""),
                r.get("CD_CVM", "001"),
                r.get("SIT", "ATIVO"),
                r.get("DT_INI_SIT", "2020-01-01"),
                r.get("TP_MERC", "BOLSA"),
                r.get("CATEG_REG", "A"),
                r.get("SETOR_ATIV", ""),
                r.get("DT_INC", "2020-01-01"),
            ],
        )


# ── load_cadastro ─────────────────────────────────────────────────────────────

def test_load_cadastro_returns_row_count(tmp_path, db):
    csv_path = _make_cad_csv(tmp_path / "cad.csv", [
        {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO",    "SETOR_ATIV": "Bancos"},
        {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "CANCELADA","SETOR_ATIV": "Alimentos"},
        {"CNPJ_CIA": "33.333.333/0001-33", "SIT": "ATIVO",    "SETOR_ATIV": ""},
    ])
    inserted = load_info_cad(db, csv_path)
    assert inserted == 3


def test_load_cadastro_table_contains_all_rows(tmp_path, db):
    csv_path = _make_cad_csv(tmp_path / "cad.csv", [
        {"CNPJ_CIA": "11.111.111/0001-11"},
        {"CNPJ_CIA": "22.222.222/0001-22"},
    ])
    load_info_cad(db, csv_path)
    count = db.execute("SELECT COUNT(*) FROM cad_cia_aberta_raw").fetchone()[0]
    assert count == 2


def test_load_cadastro_idempotent(tmp_path, db):
    """Segunda carga substitui — não acumula linhas."""
    rows = [
        {"CNPJ_CIA": "11.111.111/0001-11"},
        {"CNPJ_CIA": "22.222.222/0001-22"},
    ]
    csv_path = _make_cad_csv(tmp_path / "cad.csv", rows)
    load_info_cad(db, csv_path)
    load_info_cad(db, csv_path)
    count = db.execute("SELECT COUNT(*) FROM cad_cia_aberta_raw").fetchone()[0]
    assert count == 2


def test_load_cadastro_has_loaded_at_column(tmp_path, db):
    csv_path = _make_cad_csv(tmp_path / "cad.csv", [{"CNPJ_CIA": "11.111.111/0001-11"}])
    load_info_cad(db, csv_path)
        # Evita leitura direta de TIMESTAMPTZ (requer pytz); verifica presença via COUNT
    count = db.execute(
        "SELECT COUNT(*) FROM cad_cia_aberta_raw WHERE loaded_at IS NOT NULL"
    ).fetchone()[0]
    assert count == 1


def test_load_cadastro_preserves_cancelled_rows(tmp_path, db):
    """FR-003: linhas canceladas também devem estar na camada bruta."""
    csv_path = _make_cad_csv(tmp_path / "cad.csv", [
        {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO"},
        {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "CANCELADA"},
    ])
    load_info_cad(db, csv_path)
    cancelled = db.execute(
        "SELECT COUNT(*) FROM cad_cia_aberta_raw WHERE SIT = 'CANCELADA'"
    ).fetchone()[0]
    assert cancelled == 1


# ── classify_cadastro — pré-condição ─────────────────────────────────────────

def test_classify_raises_without_raw_table(db):
    init_info_cad_schema(db)
    with pytest.raises(RuntimeError, match="cad_cia_aberta_raw"):
        classify_info_cad(db)


# ── classify_cadastro — setor mapeado (high) ──────────────────────────────────

def test_classify_banking_high_confidence(db):
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "11.000.000/0001-11", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"}])

    counts = classify_info_cad(db)

    assert counts["high"] == 1
    assert counts["low"] == 0
    row = db.execute("SELECT profile_id, confidence FROM company_classification").fetchone()
    assert row[0] == "banking"
    assert row[1] == "high"


def test_classify_arrendamento_mercantil_banking(db):
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "22.000.000/0001-22", "SIT": "ATIVO",
                      "SETOR_ATIV": "Arrendamento Mercantil"}])
    classify_info_cad(db)
    row = db.execute("SELECT profile_id, confidence FROM company_classification").fetchone()
    assert row[0] == "banking"
    assert row[1] == "high"


def test_classify_intermediacao_financeira_banking(db):
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "23.000.000/0001-23", "SIT": "ATIVO",
                      "SETOR_ATIV": "Intermediacao Financeira"}])
    classify_info_cad(db)
    row = db.execute("SELECT profile_id, confidence FROM company_classification").fetchone()
    assert row[0] == "banking"
    assert row[1] == "high"


# ── classify_cadastro — setor não mapeado (low + evento) ─────────────────────

def test_classify_unmapped_setor_low_confidence(db):
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "33.000.000/0001-33", "SIT": "ATIVO",
                      "SETOR_ATIV": "Alimentos"}])

    counts = classify_info_cad(db)

    assert counts["low"] == 1
    row = db.execute(
        "SELECT profile_id, confidence, rule_applied FROM company_classification"
    ).fetchone()
    assert row[0] == FALLBACK_PROFILE
    assert row[1] == "low"
    assert "unmapped_setor" in row[2]


def test_classify_unmapped_creates_curation_event(db):
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "33.000.000/0001-33", "SIT": "ATIVO",
                      "SETOR_ATIV": "Alimentos"}])
    classify_info_cad(db)

    event = db.execute(
        "SELECT event_type FROM classification_curation_events"
        " WHERE cnpj_cia = '33.000.000/0001-33'"
    ).fetchone()
    assert event is not None
    assert event[0] == EVENT_UNMAPPED


# ── classify_cadastro — setor vazio (low + evento) ────────────────────────────

def test_classify_empty_setor_low_confidence(db):
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "44.000.000/0001-44", "SIT": "ATIVO", "SETOR_ATIV": ""}])

    counts = classify_info_cad(db)

    assert counts["low"] == 1
    row = db.execute("SELECT profile_id, confidence FROM company_classification").fetchone()
    assert row[0] == FALLBACK_PROFILE
    assert row[1] == "low"


def test_classify_empty_setor_creates_curation_event(db):
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "44.000.000/0001-44", "SIT": "ATIVO", "SETOR_ATIV": ""}])
    classify_info_cad(db)

    event = db.execute(
        "SELECT event_type FROM classification_curation_events"
        " WHERE cnpj_cia = '44.000.000/0001-44'"
    ).fetchone()
    assert event is not None
    assert event[0] == EVENT_EMPTY


# ── classify_cadastro — múltiplos setores distintos (ambiguidade) ─────────────

def test_classify_ambiguous_setor_low_confidence(db):
    """FR-010: CNPJ ativo com dois SETOR_ATIV distintos → confidence=low."""
    _setup_classify_schema(db)
    _insert_raw(db, [
        {"CNPJ_CIA": "55.000.000/0001-55", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
        {"CNPJ_CIA": "55.000.000/0001-55", "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"},
    ])

    counts = classify_info_cad(db)

    assert counts["low"] == 1
    row = db.execute(
        "SELECT profile_id, confidence FROM company_classification"
        " WHERE cnpj_cia = '55.000.000/0001-55'"
    ).fetchone()
    assert row[0] == FALLBACK_PROFILE
    assert row[1] == "low"


def test_classify_ambiguous_creates_curation_event(db):
    _setup_classify_schema(db)
    _insert_raw(db, [
        {"CNPJ_CIA": "55.000.000/0001-55", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
        {"CNPJ_CIA": "55.000.000/0001-55", "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"},
    ])
    classify_info_cad(db)

    event = db.execute(
        "SELECT event_type FROM classification_curation_events"
        " WHERE cnpj_cia = '55.000.000/0001-55'"
    ).fetchone()
    assert event is not None
    assert event[0] == EVENT_AMBIGUOUS


# ── classify_cadastro — apenas cancelados → excluídos da classificação ────────

def test_classify_cancelled_only_not_classified(db):
    """FR-004: linhas SIT='CANCELADA' não entram em company_classification."""
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "66.000.000/0001-66", "SIT": "CANCELADA",
                      "SETOR_ATIV": "Bancos"}])

    counts = classify_info_cad(db)

    assert counts["total"] == 0
    assert db.execute("SELECT COUNT(*) FROM company_classification").fetchone()[0] == 0


# ── classify_cadastro — FR-006: TP_MERC/CATEG_REG não afetam setor ───────────

def test_classify_different_tp_merc_same_setor_is_high(db):
    """Duplicidade por TP_MERC com mesmo SETOR_ATIV → único registro high."""
    _setup_classify_schema(db)
    _insert_raw(db, [
        {"CNPJ_CIA": "77.000.000/0001-77", "SIT": "ATIVO", "SETOR_ATIV": "Bancos",
         "TP_MERC": "BOLSA",              "DT_INI_SIT": "2020-01-01"},
        {"CNPJ_CIA": "77.000.000/0001-77", "SIT": "ATIVO", "SETOR_ATIV": "Bancos",
         "TP_MERC": "BALCAO ORGANIZADO",  "DT_INI_SIT": "2021-01-01"},
    ])

    counts = classify_info_cad(db)

    assert counts["high"] == 1
    assert counts["low"] == 0
    count = db.execute(
        "SELECT COUNT(*) FROM company_classification WHERE cnpj_cia = '77.000.000/0001-77'"
    ).fetchone()[0]
    assert count == 1


# ── classify_cadastro — determinismo por DT_INI_SIT ──────────────────────────

def test_classify_picks_most_recent_dt_ini_sit_for_descriptive_fields(db):
    """FR-015: campos descritivos vêm da linha ativa mais recente por DT_INI_SIT."""
    _setup_classify_schema(db)
    _insert_raw(db, [
        {"CNPJ_CIA": "88.000.000/0001-88", "SIT": "ATIVO", "SETOR_ATIV": "Bancos",
            "DENOM_SOCIAL": "BANCO ANTIGO", "CD_CVM": "100", "DT_INI_SIT": "2010-01-01"},
        {"CNPJ_CIA": "88.000.000/0001-88", "SIT": "ATIVO", "SETOR_ATIV": "Bancos",
            "DENOM_SOCIAL": "BANCO ATUAL",  "CD_CVM": "100", "DT_INI_SIT": "2023-01-01"},
    ])
    classify_info_cad(db)

    row = db.execute(
        "SELECT denom_social FROM company_classification WHERE cnpj_cia = '88.000.000/0001-88'"
    ).fetchone()
    assert row[0] == "BANCO ATUAL"


# ── classify_cadastro — idempotência ─────────────────────────────────────────

def test_classify_idempotent(db):
    """NFR-001: executar classify duas vezes gera o mesmo estado."""
    _setup_classify_schema(db)
    _insert_raw(db, [
        {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
        {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"},
    ])

    c1 = classify_info_cad(db)
    c2 = classify_info_cad(db)

    assert c1 == c2
    assert db.execute("SELECT COUNT(*) FROM company_classification").fetchone()[0] == 2


def test_classify_curation_events_not_duplicated_on_rerun(db):
    """FR-012: upsert por (cnpj_cia, event_type) — não duplica eventos."""
    _setup_classify_schema(db)
    _insert_raw(db, [{"CNPJ_CIA": "33.333.333/0001-33", "SIT": "ATIVO",
                      "SETOR_ATIV": "Alimentos"}])

    classify_info_cad(db)
    classify_info_cad(db)

    count = db.execute(
        "SELECT COUNT(*) FROM classification_curation_events"
        " WHERE cnpj_cia = '33.333.333/0001-33'"
    ).fetchone()[0]
    assert count == 1


# ── classify_cadastro — contagem agregada ────────────────────────────────────

def test_classify_returns_correct_counts(db):
    _setup_classify_schema(db)
    _insert_raw(db, [
        {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO",    "SETOR_ATIV": "Bancos"},
        {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "ATIVO",    "SETOR_ATIV": ""},
        {"CNPJ_CIA": "33.333.333/0001-33", "SIT": "ATIVO",    "SETOR_ATIV": "Alimentos"},
        {"CNPJ_CIA": "44.444.444/0001-44", "SIT": "CANCELADA","SETOR_ATIV": "Bancos"},
    ])

    counts = classify_info_cad(db)

    assert counts["total"] == 3   # apenas os 3 ativos
    assert counts["high"] == 1    # Bancos → banking
    assert counts["low"] == 2     # vazio + não-mapeado
