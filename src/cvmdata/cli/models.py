# Input and output models for CLI handlers
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

T = TypeVar("T")

# ============================================================================
# Outcome[T] — Structured Command Execution Result (T010)
# ============================================================================

@dataclass
class Outcome(Generic[T]):
    """Structured command execution result.
    
    Replaces inline try/except + typer.Exit patterns in handlers.
    Handlers return Outcome objects; CLI layer renders and exits.
    """
    
    status: Literal["success", "warning", "error"]
    """Result category: success (completed), warning (no-data, not failure), or error (failure)."""
    
    payload: T | None = None
    """Data returned by handler.

    Ex.: dict para download/load/normalize, int para indicators e
    list para query.
    """
    
    message: str | None = None
    """User-facing message (no technical details). Rendered with emoji prefix by render layer."""
    
    @staticmethod
    def success(message: str | None = None, payload: T | None = None) -> "Outcome[T]":
        """Command completed successfully."""
        return Outcome(status="success", message=message, payload=payload)
    
    @staticmethod
    def warning(message: str, payload: T | None = None) -> "Outcome[T]":
        """Command completed but with benign no-data condition (not a failure)."""
        return Outcome(status="warning", message=message, payload=payload)
    
    @staticmethod
    def error(message: str) -> "Outcome[T]":
        """Command failed with error; no payload."""
        return Outcome(status="error", message=message, payload=None)


# ============================================================================
# Input DTOs — Normalized from CLI options (T011, T012)
# ============================================================================

@dataclass
class DownloadInput:
    """Input for download command handler."""
    years: list[int]
    force: bool
    verbose: bool


@dataclass
class LoadInput:
    """Input for load command handler."""
    years: list[int]
    verbose: bool


@dataclass
class NormalizeInput:
    """Input for normalize command handler."""
    verbose: bool


@dataclass
class IndicatorsInput:
    """Input for indicators command handler."""
    cnpj: str | None
    verbose: bool


@dataclass
class QueryInput:
    """Input for query command handler."""
    cnpj: str | None
    year: int | None


# ============================================================================
# Query Result — Row structure for query command (T012)
# ============================================================================

@dataclass
class QueryResult:
    """Row from indicators query result.
    
    Used by query handler to return typed rows instead of raw tuples.
    """
    cnpj_cia: str
    dt_refer: str | None = None
    indicador: str | None = None
    valor: float | None = None
    n_indicadores: int | None = None  # Summary query only
    primeiro_periodo: str | None = None  # Summary query only
    ultimo_periodo: str | None = None  # Summary query only

