# Integration tests for CLI commands
from typer.testing import CliRunner

from cvmdata.cli import app

runner = CliRunner()


# ============================================================================
# CLI App Structure Tests
# ============================================================================

def test_app_help():
    """App shows help with all commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "download" in result.stdout
    assert "load" in result.stdout
    assert "normalize" in result.stdout
    assert "indicators" in result.stdout
    assert "query" in result.stdout


def test_download_help():
    """Download command has proper help."""
    result = runner.invoke(app, ["download", "--help"])
    assert result.exit_code == 0
    assert "--year" in result.stdout
    assert "--force" in result.stdout
    assert "--verbose" in result.stdout


def test_load_help():
    """Load command has proper help."""
    result = runner.invoke(app, ["load", "--help"])
    assert result.exit_code == 0
    assert "--year" in result.stdout
    assert "--verbose" in result.stdout


def test_normalize_help():
    """Normalize command has proper help."""
    result = runner.invoke(app, ["normalize", "--help"])
    assert result.exit_code == 0
    assert "--verbose" in result.stdout


def test_indicators_help():
    """Indicators command has proper help."""
    result = runner.invoke(app, ["indicators", "--help"])
    assert result.exit_code == 0
    assert "--cnpj" in result.stdout
    assert "--verbose" in result.stdout


def test_query_help():
    """Query command has proper help."""
    result = runner.invoke(app, ["query", "--help"])
    assert result.exit_code == 0
    assert "--cnpj" in result.stdout
    assert "--year" in result.stdout


# ============================================================================
# CLI Error Handling Tests (Invalid Input)
# ============================================================================

def test_download_invalid_year_too_low():
    """Download rejects year < 2000."""
    result = runner.invoke(app, ["download", "--year", "1999"])
    assert result.exit_code == 1
    assert "Invalid year" in result.stdout or "Invalid year" in result.stderr


def test_download_invalid_year_too_high():
    """Download rejects year > 3000."""
    result = runner.invoke(app, ["download", "--year", "3001"])
    assert result.exit_code == 1
    assert "Invalid year" in result.stdout or "Invalid year" in result.stderr


def test_download_invalid_year_non_numeric():
    """Download handles non-numeric year."""
    result = runner.invoke(app, ["download", "--year", "abc"])
    assert result.exit_code != 0


# ============================================================================
# CLI Exit Code Tests
# ============================================================================

def test_app_without_command_shows_help():
    """App without command shows help (no args is help)."""
    result = runner.invoke(app)
    # Exit code 0 for --help, but 2 is also acceptable for usage display
    assert result.exit_code in (0, 2)
    assert "Commands" in result.stdout or "commands" in result.stdout

