"""Parsing e validação do intervalo de anos processados pelo pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# A CVM disponibiliza dados desde 2011 (portal de dados abertos).
MIN_VALID_YEAR = 2011

# O ITR do 1º trimestre tem prazo legal de 45 dias após 31/03 (~15/05).
# Usamos junho como corte conservador: antes disso, o .zip consolidado do
# ano corrente no portal de dados abertos tende a não existir ou estar
# incompleto — pedir esse ano falharia no download, não na validação.
# É uma heurística de calendário, não uma checagem real de existência do
# arquivo (isso ficaria a cargo do downloader, se quiser mais precisão).
_CURRENT_YEAR_AVAILABLE_FROM_MONTH = 6


@dataclass(frozen=True)
class YearsParseError(ValueError):
    value: str
    invalid_years: tuple[int, ...] = ()
    min_year: int | None = None
    max_year: int | None = None

    def __str__(self) -> str:
        msg = (
            "Formato inválido para years. "
            "Use um ano (ex: 2024), lista (ex: 2021,2022,2024) "
            "ou intervalo inclusivo (ex: 2021:2025, 2020-2026)."
        )
        if self.min_year is not None and self.max_year is not None:
            msg += f" Intervalo válido: {self.min_year}-{self.max_year}."
        if self.invalid_years:
            years = ", ".join(str(y) for y in self.invalid_years)
            msg += f" Ano(s) fora do intervalo: {years}."
        return f"{msg} Recebido: {self.value!r}"


def _max_valid_year(today: date | None = None) -> int:
    """Maior ano aceito: o ano corrente, mas só a partir de junho.

    Ver docstring do módulo para o porquê do corte em junho.
    """
    today = today or date.today()
    if today.month < _CURRENT_YEAR_AVAILABLE_FROM_MONTH:
        return today.year - 1
    return today.year


def _parse_raw_years(value: str) -> list[int]:
    """Extrai a lista de anos do formato aceito, sem validar o intervalo."""
    raw = (value or "").strip()
    if not raw:
        raise YearsParseError(value=value)

    if ":" in raw or "-" in raw:
        sep = ":" if ":" in raw else "-"
        parts = [p.strip() for p in raw.split(sep) if p.strip()]
        if len(parts) != 2:
            raise YearsParseError(value=value)
        try:
            start, end = int(parts[0]), int(parts[1])
        except ValueError as exc:
            raise YearsParseError(value=value) from exc
        if start > end:
            start, end = end, start
        return list(range(start, end + 1))

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        return [int(p) for p in parts]
    except ValueError as exc:
        raise YearsParseError(value=value) from exc


def parse_years(value: str, *, today: date | None = None) -> list[int]:
    """Parseia e valida anos a partir de string.

    Formatos aceitos:
    - "2024"
    - "2021,2022,2024"
    - "2021:2025" (inclusive)
    - "2021-2025" (inclusive)

    Intervalo válido: [MIN_VALID_YEAR, ano corrente disponível] — ver
    `_max_valid_year`. Nunca corrige um valor fora do intervalo
    silenciosamente: levanta `YearsParseError` com os anos inválidos e o
    intervalo aceito, pra quem chamou decidir o que fazer (normalmente,
    parar e mostrar a mensagem pro usuário).

    `today` é injetável só para testes determinísticos.
    """
    years = _parse_raw_years(value)

    max_year = _max_valid_year(today)
    invalid = sorted({y for y in years if not (MIN_VALID_YEAR <= y <= max_year)})
    if invalid:
        raise YearsParseError(
            value=value,
            invalid_years=tuple(invalid),
            min_year=MIN_VALID_YEAR,
            max_year=max_year,
        )

    return sorted(set(years))
