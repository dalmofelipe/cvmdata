"""Testes unitários do downloader (Phase 1)."""

from __future__ import annotations

import pytest

from cvmdata.ingestion.downloader import (
    _should_extract,
    download_info_cad,
    download_zip,
)

pytestmark = pytest.mark.unit


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


def test_download_zip_skips_existing_file_without_force(tmp_path, monkeypatch):
    dest = tmp_path / "data.zip"
    dest.write_bytes(b"old")

    def fail_stream(*args, **kwargs):
        raise AssertionError("download should be skipped")

    monkeypatch.setattr("cvmdata.ingestion.downloader.httpx.stream", fail_stream)

    assert download_zip("https://example.test/data.zip", dest) == dest
    assert dest.read_bytes() == b"old"


class _FakeResponse:
    def __init__(self, chunks: list[bytes], error: Exception | None = None):
        self.chunks = chunks
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.error:
            raise self.error

    def iter_bytes(self, chunk_size: int):
        yield from self.chunks


def test_download_info_cad_removes_tmp_after_failure(tmp_path, monkeypatch):
    meta = tmp_path / "meta_cad_cia_aberta.txt"
    meta.write_text("previous", encoding="utf-8")
    calls = 0

    def stream(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _FakeResponse([b"new"])
        return _FakeResponse([b"partial"], RuntimeError("network failure"))

    monkeypatch.setattr("cvmdata.ingestion.downloader.httpx.stream", stream)

    with pytest.raises(RuntimeError, match="network failure"):
        download_info_cad("meta-url", "csv-url", tmp_path, force=True)

    assert meta.read_text(encoding="utf-8") == "new"
    assert not (tmp_path / "cad_cia_aberta.csv.tmp").exists()
    assert not (tmp_path / "meta_cad_cia_aberta.txt.tmp").exists()
