from __future__ import annotations

from pathlib import Path

import pytest

from cvmdata.config import Settings
from cvmdata.utils.database import DuckDBValidationError

pytestmark = pytest.mark.unit


def test_settings_builds_source_urls_and_data_paths(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        itr_url_template="https://itr.test/{year}.zip",
        dfp_url_template="https://dfp.test/{year}.zip",
    )

    assert settings.itr_url(2024) == "https://itr.test/2024.zip"
    assert settings.dfp_url(2024) == "https://dfp.test/2024.zip"
    assert settings.raw_dir == tmp_path / "raw"
    assert settings.db_path == tmp_path / "db" / "cvmdata.duckdb"


def test_settings_validates_duckdb_threads_lazily():
    settings = Settings(duckdb_threads=0)

    with pytest.raises(DuckDBValidationError):
        _ = settings.sanitized_duckdb_threads
