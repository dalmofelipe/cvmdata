"""Testes unitários do downloader (Phase 1)."""

from __future__ import annotations

import pytest

from cvmdata.ingestion.downloader import _should_extract


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("itr_cia_aberta_BPA_con_2024.csv", True),
        ("dfp_cia_aberta_DMPL_ind_2021.csv", False),
        ("itr_cia_aberta_DRE_con_2022.csv", True),
        ("itr_cia_aberta_DFC_MD_con_2024.csv", False),
        ("itr_cia_aberta_composicao_capital_2024.csv", True),
        ("itr_cia_aberta_parecer_2024.csv", False),
        ("itr_cia_aberta_2024.csv", False),
        ("README.txt", False),
    ],
)
def test_should_extract(filename: str, expected: bool):
    assert _should_extract(filename) == expected


def test_extract_zip_creates_csvs(tmp_path):
    """extract_zip deve extrair CSVs do catálogo, ignorando os demais."""
    import zipfile

    from cvmdata.ingestion.downloader import extract_zip

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("itr_cia_aberta_BPA_con_2024.csv", "col1\nval1")
        zf.writestr("itr_cia_aberta_composicao_capital_2024.csv", "col1\nval1")
        zf.writestr("itr_cia_aberta_parecer_2024.csv", "col1\nval1")
        zf.writestr("itr_cia_aberta_2024.csv", "col1\nval1")

    dest = tmp_path / "out"
    extracted = extract_zip(zip_path, dest)

    assert len(extracted) == 2
    assert extracted[0].name == "itr_cia_aberta_BPA_con_2024.csv"
    assert extracted[1].name == "itr_cia_aberta_composicao_capital_2024.csv"
