"""Validation helpers for CLI inputs."""

from __future__ import annotations

from cvmdata.cli.constants import (
    INDICATORS_YEAR_MAX,
    INDICATORS_YEAR_MIN,
    INFO_CAD_PAGE_SIZE_MAX,
    INFO_CAD_PAGE_SIZE_MIN,
)


class ValidationError(ValueError):
    """Raised when a CLI option fails validation."""


def validate_indicators_year(year: int | None) -> None:
    """Validate optional indicators year filter."""
    if year is None:
        return

    if not (INDICATORS_YEAR_MIN <= year <= INDICATORS_YEAR_MAX):
        raise ValidationError(
            f"Ano inválido (deve estar entre {INDICATORS_YEAR_MIN} e {INDICATORS_YEAR_MAX})"
        )


def validate_info_cad_page(page: int) -> None:
    """Validate info-cad page number."""
    if page < 1:
        raise ValidationError("Página inválida (deve ser >= 1)")


def validate_info_cad_page_size(page_size: int) -> None:
    """Validate info-cad summary page size."""
    if page_size < INFO_CAD_PAGE_SIZE_MIN or page_size > INFO_CAD_PAGE_SIZE_MAX:
        raise ValidationError(
            "Tamanho de página inválido "
            f"(deve estar entre {INFO_CAD_PAGE_SIZE_MIN} e {INFO_CAD_PAGE_SIZE_MAX})"
        )
