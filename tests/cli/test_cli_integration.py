"""Testes de integração do CLI via Typer CliRunner."""

from __future__ import annotations

from datetime import datetime, timezone

from typer.testing import CliRunner

from cvmdata.cli import app, handlers
from cvmdata.cli.models import IndicatorsResult, InfoCadResult, Outcome
from cvmdata.pipeline.models import PipelineReport, StepReport

runner = CliRunner()


def test_app_help_lists_all_commands() -> None:
    """Ajuda principal deve listar todos os comandos esperados."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "indicators" in result.stdout
    assert "info-cad" in result.stdout
    assert "pipeline" in result.stdout


def _patch_handle(monkeypatch, module_obj, outcome: Outcome) -> None:
    """Aplica patch do handler para retornar outcome determinístico."""

    def fake_handle(_input):
        return outcome

    # Se for handlers.indicators ou handlers.info_cad, patchar o submódulo
    if hasattr(module_obj, "indicators"):
        monkeypatch.setattr(module_obj.indicators, "handle", fake_handle)
    elif hasattr(module_obj, "info_cad"):
        monkeypatch.setattr(module_obj.info_cad, "handle", fake_handle)
    else:
        monkeypatch.setattr(module_obj, "handle", fake_handle)


def test_indicators_command_requires_cnpj() -> None:
    result = runner.invoke(app, ["indicators"])
    assert result.exit_code != 0
    assert "--cnpj" in (result.stdout + result.stderr)


def test_indicators_command_detail_table(monkeypatch) -> None:
    """Indicators com CNPJ deve renderizar tabela de detalhe e sair com 0."""
    outcome = Outcome.success(
        payload=[
            IndicatorsResult(
                cnpj_cia="00.000.000/0001-91",
                dt_refer="2024-12-31",
                indicador="ROE",
                valor=0.1234,
            )
        ]
    )
    _patch_handle(monkeypatch, handlers.indicators, outcome)

    result = runner.invoke(app, ["indicators", "--cnpj", "00.000.000/0001-91"])
    assert result.exit_code == 0
    assert "Indicadores" in result.stdout


def test_indicators_command_warning(monkeypatch) -> None:
    """Indicators com warning deve sair com 0 e exibir aviso."""
    _patch_handle(
        monkeypatch,
        handlers.indicators,
        Outcome.warning(message="sem resultados", payload=[]),
    )

    result = runner.invoke(app, ["indicators", "--cnpj", "99.999.999/0001-99"])
    assert result.exit_code == 0
    assert "⚠" in result.stdout


def test_indicators_command_error(monkeypatch) -> None:
    """Indicators com erro deve sair com 1 e exibir mensagem em stderr."""
    _patch_handle(monkeypatch, handlers.indicators, Outcome.error(message="erro"))

    result = runner.invoke(app, ["indicators", "--cnpj", "00.000.000/0001-91"])
    assert result.exit_code == 1
    assert "✗" in result.stderr


def test_info_cad_command_summary_table(monkeypatch) -> None:
    """Info-cad sem CNPJ deve renderizar tabela de resumo."""
    outcome = Outcome.success(
        payload=[
            InfoCadResult(
                cnpj_cia="00.000.000/0001-91",
                denom_social="Banco X",
                setor_ativ="Financial",
                profile_id="high",
                confidence=0.95,
                updated_at="2024-01-01",
            )
        ]
    )
    _patch_handle(monkeypatch, handlers.info_cad, outcome)

    result = runner.invoke(app, ["info-cad"])
    assert result.exit_code == 0
    assert "company_classification" in result.stdout


def test_info_cad_command_detail_table(monkeypatch) -> None:
    """Info-cad com CNPJ deve renderizar tabela de detalhe."""
    outcome = Outcome.success(
        payload=[
            InfoCadResult(
                cnpj_cia="00.000.000/0001-91",
                cd_cvm="1234",
                denom_social="Banco X",
                denom_comerc="Banco X SA",
                setor_ativ="Financial",
                profile_id="high",
                confidence=0.95,
                rule_applied="rule_1",
                updated_at="2024-01-01",
            )
        ]
    )
    _patch_handle(monkeypatch, handlers.info_cad, outcome)

    result = runner.invoke(app, ["info-cad", "--cnpj", "00.000.000/0001-91"])
    assert result.exit_code == 0
    assert "Classificação" in result.stdout


def test_pipeline_run_invalid_years() -> None:
    result = runner.invoke(app, ["pipeline", "run", "--years", "1999"])
    assert result.exit_code == 1
    assert "Formato inválido" in (result.stdout + result.stderr)


def test_pipeline_run_delegates_to_orchestrator(monkeypatch) -> None:
    from cvmdata.cli import cli as cli_module

    fake_report = PipelineReport(
        name="full",
        status="success",
        steps=[
            StepReport(
                name="download_financial",
                status="success",
                message="ok",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        ],
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )

    def fake_run_full(*, years, force_download=False, cnpj=None, **kwargs):
        assert years == [2024]
        assert force_download is True
        assert cnpj == "00.000.000/0001-91"
        return fake_report

    monkeypatch.setattr(cli_module, "run_full", fake_run_full)

    result = runner.invoke(
        app,
        [
            "pipeline",
            "run",
            "--years",
            "2024",
            "--force-download",
            "--cnpj",
            "00.000.000/0001-91",
        ],
    )
    assert result.exit_code == 0
    assert "Pipeline" in result.stdout
