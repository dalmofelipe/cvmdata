"""Testes unitários do loader (Phase 1)."""
from __future__ import annotations

from pathlib import Path

import pytest

from cvmdata.ingestion.db import init_schema
from cvmdata.ingestion.loader import load_csv, load_source_year, parse_csv_filename

# ── Helpers ─────────────────────────────────────────────────────────────────

# Códigos reais do ACCOUNT_MAP usados nos fixtures
_BPA_CODES = ["1", "1.01", "1.01.01", "1.01.02", "1.01.04", "1.02", "1.02.01",
              "2", "2.01", "2.01.04", "2.02", "2.02.01", "2.03"]
_DRE_CODES = ["3.01", "3.03", "3.05", "3.06.02", "3.11"]


def _make_bpa_csv(path: Path, rows: int = 3) -> Path:
    """Cria um CSV mínimo de BPA/BPP (14 cols, sem DT_INI_EXERC)."""
    header = "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"  # noqa: E501
    lines = [header]
    for i in range(rows):
        cd = _BPA_CODES[i % len(_BPA_CODES)]
        lines.append(
            f"00.000.000/0001-91;2024-03-31;1;EMPRESA TEST;001000;"
            f"DF Consolidado;REAL;MIL;ÚLTIMO;2024-03-31;"
            f"{cd};Conta {i};{1000 + i * 100}.0;S"
        )
    path.write_bytes("\n".join(lines).encode("latin1"))
    return path


def _make_flow_csv(path: Path, rows: int = 3) -> Path:
    """Cria um CSV mínimo de demo FLOW (15 cols, com DT_INI_EXERC)."""
    header = "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"  # noqa: E501
    lines = [header]
    for i in range(rows):
        cd = _DRE_CODES[i % len(_DRE_CODES)]
        lines.append(
            f"00.000.000/0001-91;2024-03-31;1;EMPRESA TEST;001000;"
            f"DF Consolidado;REAL;MIL;ÚLTIMO;2024-01-01;2024-03-31;"
            f"{cd};Conta {i};{1000 + i * 100}.0;S"
        )
    path.write_bytes("\n".join(lines).encode("latin1"))
    return path


# ── Testes: parse_csv_filename ───────────────────────────────────────────────

@pytest.mark.parametrize(
    "filename, expected",
    [
        ("itr_cia_aberta_BPA_con_2024.csv", ("BPA", "con", "itr", 2024)),
        ("itr_cia_aberta_DRE_con_2024.csv", ("DRE", "con", "itr", 2024)),
        ("dfp_cia_aberta_BPP_con_2021.csv", ("BPP", "con", "dfp", 2021)),
    ],
)
def test_parse_csv_filename_valid(tmp_path, filename, expected):
    result = parse_csv_filename(tmp_path / filename)
    assert result == expected


@pytest.mark.parametrize(
    "filename",
    [
        "itr_cia_aberta_composicao_capital_2024.csv",  # sem scope
        "itr_cia_aberta_parecer_2024.csv",             # sem scope
        "itr_cia_aberta_2024.csv",                     # índice
        "outro_arquivo.csv",                           # padrão diferente
        "dfp_cia_aberta_BPP_ind_2021.csv",             # individual — ignorado
        "dfp_cia_aberta_DFC_MD_con_2021.csv",          # fora de INDICATOR_DEMOS
        "dfp_cia_aberta_DFC_MD_ind_2021.csv",          # individual + fora de INDICATOR_DEMOS
        "itr_cia_aberta_DMPL_con_2023.csv",            # fora de INDICATOR_DEMOS
        "itr_cia_aberta_DRA_con_2024.csv",             # fora de INDICATOR_DEMOS
    ],
)
def test_parse_csv_filename_invalid(tmp_path, filename):
    result = parse_csv_filename(tmp_path / filename)
    assert result is None


# ── Testes: load_csv ─────────────────────────────────────────────────────────

def test_load_csv_inserts_rows(tmp_path, db):
    """load_csv deve inserir linhas corretamente na tabela raw_bpa."""
    init_schema(db)
    csv_path = _make_bpa_csv(tmp_path / "itr_cia_aberta_BPA_con_2024.csv", rows=5)

    count = load_csv(db, csv_path, "BPA", "itr", 2024, "con")

    assert count == 5
    row = db.execute(
        "SELECT source, year, scope FROM raw_bpa WHERE source='itr' LIMIT 1"
    ).fetchone()
    assert row == ("itr", 2024, "con")


def test_load_csv_idempotent(tmp_path, db):
    """Carregar o mesmo CSV duas vezes não deve duplicar linhas."""
    init_schema(db)
    csv_path = _make_bpa_csv(tmp_path / "itr_cia_aberta_BPA_con_2024.csv", rows=4)

    load_csv(db, csv_path, "BPA", "itr", 2024, "con")
    load_csv(db, csv_path, "BPA", "itr", 2024, "con")

    count = db.execute(
        "SELECT COUNT(*) FROM raw_bpa WHERE source='itr' AND year=2024 AND scope='con'"
    ).fetchone()[0]
    assert count == 4


# ── Testes: load_source_year ─────────────────────────────────────────────────

def test_load_source_year_returns_empty_when_no_dir(tmp_path, db):
    """Sem diretório de CSVs deve retornar dict vazio (não erro)."""
    results = load_source_year(db, "itr", 2024, tmp_path)
    assert results == {}


def test_load_source_year_scans_all_demos(tmp_path, db):
    """Deve carregar múltiplos demos (de grupos diferentes) quando existem CSVs."""
    init_schema(db)
    csv_dir = tmp_path / "itr" / "2024"
    csv_dir.mkdir(parents=True)

    # BALANCE group (14 cols)
    _make_bpa_csv(csv_dir / "itr_cia_aberta_BPA_con_2024.csv", rows=2)
    _make_bpa_csv(csv_dir / "itr_cia_aberta_BPP_con_2024.csv", rows=2)
    # FLOW group (15 cols)
    _make_flow_csv(csv_dir / "itr_cia_aberta_DRE_con_2024.csv", rows=2)

    results = load_source_year(db, "itr", 2024, tmp_path)

    assert len(results) == 3
    assert "BPA/con" in results
    assert "BPP/con" in results
    assert "DRE/con" in results


def test_load_source_year_skips_non_demo_files(tmp_path, db):
    """composicao_capital e parecer não devem ser carregados."""
    init_schema(db)
    csv_dir = tmp_path / "itr" / "2024"
    csv_dir.mkdir(parents=True)

    _make_bpa_csv(csv_dir / "itr_cia_aberta_BPA_con_2024.csv", rows=2)
    # Arquivo que deve ser ignorado
    (csv_dir / "itr_cia_aberta_composicao_capital_2024.csv").write_bytes(b"col1\nval1")

    results = load_source_year(db, "itr", 2024, tmp_path)

    assert list(results.keys()) == ["BPA/con"]
