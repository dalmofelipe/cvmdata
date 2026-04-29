from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class YearsParseError(ValueError):
    value: str

    def __str__(self) -> str:
        return (
            "Formato inválido para --years. "
            "Use um ano (ex: 2024), lista (ex: 2021,2022,2024) "
            "ou intervalo inclusivo (ex: 2021:2025). "
            f"Recebido: {self.value!r}"
        )


def parse_years(value: str) -> list[int]:
    """Parseia anos a partir de string.

    Formatos aceitos:
    - "2024"
    - "2021,2022,2024"
    - "2021:2025" (inclusive)
    - "2021-2025" (inclusive)
    """
    raw = (value or "").strip()
    if not raw:
        raise YearsParseError(value=value)

    # Range
    if ":" in raw or "-" in raw:
        sep = ":" if ":" in raw else "-"
        parts = [p.strip() for p in raw.split(sep) if p.strip()]
        if len(parts) != 2:
            raise YearsParseError(value=value)
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError as exc:
            raise YearsParseError(value=value) from exc
        if start > end:
            start, end = end, start
        years = list(range(start, end + 1))
    else:
        # List or single
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        try:
            years = [int(p) for p in parts]
        except ValueError as exc:
            raise YearsParseError(value=value) from exc

    # Basic sanity check (keep same semantics used in CLI before)
    for year in years:
        if not (2000 <= year <= 3000):
            raise YearsParseError(value=value)

    return sorted(set(years))
