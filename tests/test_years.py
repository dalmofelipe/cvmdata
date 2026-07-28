from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cvmdata.config import Settings
from cvmdata.utils.years import YearsParseError, _max_valid_year, parse_years

# Data de referência fixa nos testes de parsing — evita testes que dependem
# do dia em que são rodados (ex: "2024" só ser válido enquanto for <= ano atual).
_REF_TODAY = date(2026, 7, 21)  # mês >= 6: ano corrente (2026) já disponível


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2024", [2024]),
        ("2021,2022,2024", [2021, 2022, 2024]),
        ("2021:2023", [2021, 2022, 2023]),
        ("2021-2023", [2021, 2022, 2023]),
        ("2023:2021", [2021, 2022, 2023]),
        ("2026", [2026]),  # ano corrente, dentro do intervalo válido
    ],
)
def test_parse_years_accepts_list_and_ranges(value: str, expected: list[int]) -> None:
    assert parse_years(value, today=_REF_TODAY) == expected


@pytest.mark.parametrize(
    "value",
    ["", "2021:2023,2025", "2021:bad", "2010", "2027", "2000:2030"],
)
def test_parse_years_rejects_invalid_values(value: str) -> None:
    with pytest.raises(YearsParseError):
        parse_years(value, today=_REF_TODAY)


def test_parse_years_error_reports_valid_range_and_offending_years() -> None:
    with pytest.raises(YearsParseError) as exc_info:
        parse_years("2000:2030", today=_REF_TODAY)

    message = str(exc_info.value)
    assert "2011-2026" in message
    assert "2000" in message
    assert "2030" in message


@pytest.mark.parametrize(
    "today, expected_max_year",
    [
        (date(2026, 1, 15), 2025),  # janeiro: 1º ITR ainda nem venceu (15/05)
        (date(2026, 5, 14), 2025),  # véspera do prazo legal do 1º ITR
        (date(2026, 5, 16), 2025),  # dia seguinte ao prazo, ainda dentro da margem
        (date(2026, 6, 1), 2026),  # corte: ano corrente passa a ser aceito
        (date(2026, 12, 31), 2026),
    ],
)
def test_max_valid_year_heuristic(today: date, expected_max_year: int) -> None:
    assert _max_valid_year(today) == expected_max_year


def test_settings_years_list_env_overrides_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("CVM_YEARS=2020:2022\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CVM_YEARS", "2021,2023")

    settings = Settings()

    assert settings.years_list == [2021, 2023]


def test_settings_years_list_raises_on_out_of_range(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CVM_YEARS", "2000:2030")

    settings = Settings()

    with pytest.raises(YearsParseError):
        settings.years_list
