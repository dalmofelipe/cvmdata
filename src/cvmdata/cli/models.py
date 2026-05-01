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

    cnpj: str
    year: int | None = None


@dataclass
class InfoCadInput:
    """Input for info-cad command handler."""

    cnpj: str | None = None
    verbose: bool = False


# ============================================================================
# Query Result — Row structure for query command (T012)
# ============================================================================


@dataclass
class IndicatorsResult:
    """Row from indicators query result."""

    cnpj_cia: str
    dt_refer: str | None = None
    indicador: str | None = None
    valor: float | None = None


# ============================================================================
# Informações Cadastrais DTOs — Input and Output for informacoes cadastrais commands
# ============================================================================


@dataclass
class DownloadInfoCadInput:
    """Input for download-info-cad command handler."""

    force: bool
    verbose: bool


@dataclass
class LoadInfoCadInput:
    """Input for load-cad command handler."""

    verbose: bool


@dataclass
class ClassifyInfoCadInput:
    """Input for classify-info-cad command handler."""

    verbose: bool


# InfoCadInput já definido acima


@dataclass
class ClassifyInfoCadResult:
    """Output from classify-info-cad handler."""

    total: int
    """Total number of CNPJs classified."""
    high: int
    """Number of 'high' profile classifications."""
    low: int
    """Number of 'low' profile classifications."""


@dataclass
class InfoCadResult:
    """Row from info-cad result (summary or detail)."""

    cnpj_cia: str
    denom_social: str | None = None
    setor_ativ: str | None = None
    profile_id: str | None = None
    confidence: float | str | None = None
    updated_at: str | None = None
    # Additional fields for detail query
    cd_cvm: str | None = None
    denom_comerc: str | None = None
    rule_applied: str | None = None
