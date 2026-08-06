"""Validadores e sanitizadores para configurações e parâmetros de conexões."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MEMORY_LIMIT_REGEX = re.compile(r"^[1-9]\d*(\.\d+)?\s*(MB|GB|%)$", re.IGNORECASE)


@dataclass(frozen=True)
class DuckDBValidationError(ValueError):
    """Exceção customizada para parâmetros inválidos do DuckDB."""

    param_name: str
    value: object
    reason: str

    def __str__(self) -> str:
        return f"Parâmetro inválido '{self.param_name}'={self.value!r}: {self.reason}"


def sanitize_duckdb_memory_limit(memory_limit: str | None) -> str | None:
    """Valida o formato do limite de memória para o DuckDB."""
    if memory_limit is None:
        return None

    value_clean = memory_limit.strip()

    if not _MEMORY_LIMIT_REGEX.match(value_clean):
        raise DuckDBValidationError(
            param_name="memory_limit",
            value=memory_limit,
            reason="Use um número positivo seguido de MB, GB ou % (ex: '2GB', '500MB', '80%').",
        )

    return value_clean.upper()


def sanitize_duckdb_threads(threads: int | None) -> int | None:
    """Valida a quantidade de threads para o DuckDB."""
    if threads is None:
        return None
    
    if threads <= 0:
        raise DuckDBValidationError(
            param_name="threads",
            value=threads,
            reason="O número de threads deve ser maior que 0.",
        )
    
    return threads