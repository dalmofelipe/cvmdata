from __future__ import annotations

import pytest

from cvmdata.cli.validation import (
    ValidationError,
    validate_indicators_year,
    validate_info_cad_page,
    validate_info_cad_page_size,
)


def test_validate_indicators_year_accepts_none() -> None:
    validate_indicators_year(None)


def test_validate_indicators_year_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError, match="Ano inválido"):
        validate_indicators_year(1999)


def test_validate_info_cad_page_rejects_zero() -> None:
    with pytest.raises(ValidationError, match="Página inválida"):
        validate_info_cad_page(0)


def test_validate_info_cad_page_size_rejects_too_small() -> None:
    with pytest.raises(ValidationError, match="Tamanho de página inválido"):
        validate_info_cad_page_size(19)
