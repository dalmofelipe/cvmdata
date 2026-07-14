from __future__ import annotations

from pathlib import Path

import pytest

from cvmdata.config import Settings
from cvmdata.core.years import YearsParseError, parse_years


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2024", [2024]),
        ("2021,2022,2024", [2021, 2022, 2024]),
        ("2021:2023", [2021, 2022, 2023]),
        ("2021-2023", [2021, 2022, 2023]),
        ("2023:2021", [2021, 2022, 2023]),
    ],
)
def test_parse_years_accepts_list_and_ranges(value: str, expected: list[int]) -> None:
    assert parse_years(value) == expected


@pytest.mark.parametrize("value", ["", "2021:2023,2025", "1999", "2021:bad"])
def test_parse_years_rejects_invalid_values(value: str) -> None:
    with pytest.raises(YearsParseError):
        parse_years(value)


def test_settings_years_list_env_overrides_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("CVM_YEARS=2020:2022\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CVM_YEARS", "2021,2023")

    settings = Settings()

    assert settings.years_list == [2021, 2023]
