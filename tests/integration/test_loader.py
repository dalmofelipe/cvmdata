"""Testes de integração do loader e ingestão em DuckDB."""

from __future__ import annotations

import pytest

from cvmdata.ingestion.catalog import DatasetType
from cvmdata.ingestion.db import init_schema
from cvmdata.ingestion.loader import (
    _match_dataset,
    load_b3_tickers,
    load_csv,
    load_source_year,
)
from tests.support import make_b3_tickers_json, make_balance_csv, make_flow_csv

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "filename, expected_key, expected_type",
    [
        ("itr_cia_aberta_BPA_con_2024.csv", "BPA", DatasetType.STATEMENT),
        ("itr_cia_aberta_DRE_con_2024.csv", "DRE", DatasetType.STATEMENT),
        ("dfp_cia_aberta_BPP_con_2021.csv", "BPP", DatasetType.STATEMENT),
        ("itr_cia_aberta_composicao_capital_2024.csv", "COMPOSICAO_CAPITAL", DatasetType.DIRECT_INSERT),
        ("dfp_cia_aberta_composicao_capital_2024.csv", "COMPOSICAO_CAPITAL", DatasetType.DIRECT_INSERT),
    ],
)
def test_match_dataset_valid(filename, expected_key, expected_type):
    result = _match_dataset(filename)
    assert result == (expected_key, expected_type)


@pytest.mark.parametrize(
    "filename",
    [
        "itr_cia_aberta_parecer_2024.csv",
        "itr_cia_aberta_2024.csv",
        "outro_arquivo.csv",
        "dfp_cia_aberta_BPP_ind_2021.csv",
        "dfp_cia_aberta_DFC_MD_con_2021.csv",
        "dfp_cia_aberta_DFC_MD_ind_2021.csv",
        "itr_cia_aberta_DMPL_con_2023.csv",
        "itr_cia_aberta_DRA_con_2024.csv",
    ],
)
def test_match_dataset_invalid(filename):
    result = _match_dataset(filename)
    assert result is None


def test_load_csv_inserts_rows(tmp_path, db):
    init_schema(db)
    csv_path = make_balance_csv(tmp_path / "itr_cia_aberta_BPA_con_2024.csv", rows=5)

    count = load_csv(db, csv_path, "BPA", "itr", 2024, "con")

    assert count == 5
    row = db.execute(
        "SELECT source, year, scope FROM raw_bpa WHERE source='itr' LIMIT 1"
    ).fetchone()
    assert row == ("itr", 2024, "con")


def test_load_csv_idempotent(tmp_path, db):
    init_schema(db)
    csv_path = make_balance_csv(tmp_path / "itr_cia_aberta_BPA_con_2024.csv", rows=4)

    load_csv(db, csv_path, "BPA", "itr", 2024, "con")
    load_csv(db, csv_path, "BPA", "itr", 2024, "con")

    count = db.execute(
        "SELECT COUNT(*) FROM raw_bpa WHERE source='itr' AND year=2024 AND scope='con'"
    ).fetchone()[0]
    assert count == 4


def test_load_csv_rejects_invalid_scope(tmp_path, db):
    init_schema(db)
    csv_path = make_balance_csv(tmp_path / "itr_cia_aberta_BPA_con_2024.csv", rows=1)

    with pytest.raises(ValueError, match="apenas 'con'"):
        load_csv(db, csv_path, "BPA", "itr", 2024, "ind")


def test_load_source_year_returns_empty_when_no_dir(tmp_path, db):
    results = load_source_year(db, "itr", 2024, tmp_path)
    assert results == {}


def test_load_source_year_scans_all_demos(tmp_path, db):
    init_schema(db)
    csv_dir = tmp_path / "itr" / "2024"
    csv_dir.mkdir(parents=True)

    make_balance_csv(csv_dir / "itr_cia_aberta_BPA_con_2024.csv", rows=2)
    make_balance_csv(csv_dir / "itr_cia_aberta_BPP_con_2024.csv", rows=2)
    make_flow_csv(csv_dir / "itr_cia_aberta_DRE_con_2024.csv", rows=2)

    results = load_source_year(db, "itr", 2024, tmp_path)

    assert len(results) == 3
    assert "BPA" in results
    assert "BPP" in results
    assert "DRE" in results


def test_load_source_year_loads_composicao_capital(tmp_path, db):
    init_schema(db)
    csv_dir = tmp_path / "itr" / "2024"
    csv_dir.mkdir(parents=True)

    make_balance_csv(csv_dir / "itr_cia_aberta_BPA_con_2024.csv", rows=2)
    header = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;"
        "QT_ACAO_ORDIN_CAP_INTEGR;QT_ACAO_PREF_CAP_INTEGR;QT_ACAO_TOTAL_CAP_INTEGR;"
        "QT_ACAO_ORDIN_TESOURO;QT_ACAO_PREF_TESOURO;QT_ACAO_TOTAL_TESOURO"
    )
    cc_path = csv_dir / "itr_cia_aberta_composicao_capital_2024.csv"
    cc_path.write_text(
        header + "\n"
        "00.000.000/0001-91;2024-03-31;1;EMPRESA TEST;"
        "1000000;500000;1500000;10000;5000;15000\n",
        encoding="latin1",
    )

    results = load_source_year(db, "itr", 2024, tmp_path)

    assert "BPA" in results
    assert "COMPOSICAO_CAPITAL" in results
    cc_count = db.execute(
        "SELECT COUNT(*) FROM composicao_capital WHERE source='itr' AND year=2024"
    ).fetchone()[0]
    assert cc_count == 1


def test_load_b3_tickers_inserts_active_rows(tmp_path, db):
    tickers_dir = tmp_path / "b3_tickers"
    tickers_dir.mkdir(parents=True)
    make_b3_tickers_json(tickers_dir / "page_1.json")

    count = load_b3_tickers(db, tickers_dir)

    assert count == 1
    row = db.execute(
        (
            "SELECT cod_cvm, ticker_root, company_name, trading_name, "
            "cnpj_digits, status FROM b3_tickers"
        )
    ).fetchone()
    assert row == (1234, "ABCD", "ABC COMPANHIA", "ABC", "12345678000190", "A")


def test_load_b3_tickers_is_idempotent(tmp_path, db):
    tickers_dir = tmp_path / "b3_tickers"
    tickers_dir.mkdir(parents=True)
    make_b3_tickers_json(tickers_dir / "page_1.json")

    load_b3_tickers(db, tickers_dir)
    load_b3_tickers(db, tickers_dir)

    count = db.execute("SELECT COUNT(*) FROM b3_tickers").fetchone()[0]
    assert count == 1
