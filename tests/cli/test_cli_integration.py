"""Testes de integração do CLI via Typer CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from cvmdata.cli import app, handlers
from cvmdata.cli.models import Outcome, QueryInfoCadResult, QueryResult

runner = CliRunner()


def test_app_help_lists_all_commands() -> None:
    """Ajuda principal deve listar todos os comandos esperados."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "download" in result.stdout
    assert "load" in result.stdout
    assert "normalize" in result.stdout
    assert "indicators" in result.stdout
    assert "query" in result.stdout
    assert "download-info-cad" in result.stdout
    assert "load-info-cad" in result.stdout
    assert "classify-info-cad" in result.stdout
    assert "query-info-cad" in result.stdout


def test_download_command_invalid_year() -> None:
    """Download deve rejeitar ano fora do intervalo permitido."""
    result = runner.invoke(app, ["download", "--year", "1999"])
    assert result.exit_code == 1
    assert "Ano inválido" in (result.stdout + result.stderr)


def _patch_handle(monkeypatch, module_obj, outcome: Outcome) -> None:
    """Aplica patch do handler para retornar outcome determinístico."""

    def fake_handle(_input):
        return outcome

    monkeypatch.setattr(module_obj, "handle", fake_handle)


def test_download_command_delegates_to_handler_success(monkeypatch) -> None:
    """Comando download deve delegar para handler e sair com código 0 em sucesso."""
    _patch_handle(monkeypatch, handlers.download, Outcome.success(message="ok"))
    result = runner.invoke(app, ["download", "--year", "2024"])
    assert result.exit_code == 0
    assert "✓" in result.stdout


def test_load_command_delegates_to_handler_warning(monkeypatch) -> None:
    """Comando load deve retornar warning sem falhar o processo."""
    _patch_handle(monkeypatch, handlers.load, Outcome.warning(message="sem dados"))
    result = runner.invoke(app, ["load", "--year", "2024"])
    assert result.exit_code == 0
    assert "⚠" in result.stdout


def test_normalize_command_delegates_to_handler_error(monkeypatch) -> None:
    """Comando normalize deve sair com código 1 em erro."""
    _patch_handle(monkeypatch, handlers.normalize, Outcome.error(message="falha"))
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 1
    assert "✗" in result.stderr


def test_indicators_command_delegates_to_handler(monkeypatch) -> None:
    """Comando indicators deve delegar com filtro opcional de CNPJ."""
    _patch_handle(monkeypatch, handlers.indicators, Outcome.success(message="ok", payload=10))
    result = runner.invoke(app, ["indicators", "--cnpj", "00.000.000/0001-91"])
    assert result.exit_code == 0
    assert "✓" in result.stdout


def test_query_command_summary_table(monkeypatch) -> None:
    """Query sem CNPJ deve renderizar tabela de resumo e sair com 0."""
    outcome = Outcome.success(
        payload=[
            QueryResult(
                cnpj_cia="00.000.000/0001-91",
                n_indicadores=10,
                primeiro_periodo="2021-12-31",
                ultimo_periodo="2024-12-31",
            )
        ]
    )
    _patch_handle(monkeypatch, handlers.query, outcome)

    result = runner.invoke(app, ["query"])
    assert result.exit_code == 0
    assert "Top 10 empresas" in result.stdout


def test_query_command_detail_table(monkeypatch) -> None:
    """Query com CNPJ deve renderizar tabela de detalhe e sair com 0."""
    outcome = Outcome.success(
        payload=[
            QueryResult(
                cnpj_cia="00.000.000/0001-91",
                dt_refer="2024-12-31",
                indicador="ROE",
                valor=0.1234,
            )
        ]
    )
    _patch_handle(monkeypatch, handlers.query, outcome)

    result = runner.invoke(app, ["query", "--cnpj", "00.000.000/0001-91"])
    assert result.exit_code == 0
    assert "Indicadores" in result.stdout


def test_query_command_warning(monkeypatch) -> None:
    """Query com warning deve sair com 0 e exibir aviso."""
    _patch_handle(
        monkeypatch,
        handlers.query,
        Outcome.warning(message="sem resultados", payload=[]),
    )

    result = runner.invoke(app, ["query", "--cnpj", "99.999.999/0001-99"])
    assert result.exit_code == 0
    assert "⚠" in result.stdout


def test_query_command_error(monkeypatch) -> None:
    """Query com erro deve sair com 1 e exibir mensagem em stderr."""
    _patch_handle(monkeypatch, handlers.query, Outcome.error(message="erro"))

    result = runner.invoke(app, ["query", "--cnpj", "00.000.000/0001-91"])
    assert result.exit_code == 1
    assert "✗" in result.stderr


def test_download_info_cad_command_delegates_to_handler(monkeypatch) -> None:
    """Comando download-info-cad deve delegar ao handler e sair com 0 em sucesso."""
    _patch_handle(monkeypatch, handlers.download_info_cad, Outcome.success(message="ok"))

    result = runner.invoke(app, ["download-info-cad", "--force"])
    assert result.exit_code == 0
    assert "✓" in result.stdout


def test_load_info_cad_command_warning(monkeypatch) -> None:
    """Comando load-info-cad com warning não deve falhar processo."""
    _patch_handle(monkeypatch, handlers.load_info_cad, Outcome.warning(message="sem arquivo"))

    result = runner.invoke(app, ["load-info-cad"])
    assert result.exit_code == 0
    assert "⚠" in result.stdout


def test_classify_info_cad_command_error(monkeypatch) -> None:
    """Comando classify-info-cad deve sair com 1 em erro."""
    _patch_handle(monkeypatch, handlers.classify_info_cad, Outcome.error(message="falha"))

    result = runner.invoke(app, ["classify-info-cad"])
    assert result.exit_code == 1
    assert "✗" in result.stderr


def test_query_info_cad_command_summary_table(monkeypatch) -> None:
    """Query-info-cad sem CNPJ deve renderizar tabela de resumo."""
    outcome = Outcome.success(
        payload=[
            QueryInfoCadResult(
                cnpj_cia="00.000.000/0001-91",
                denom_social="Banco X",
                setor_ativ="Financial",
                profile_id="high",
                confidence=0.95,
                updated_at="2024-01-01",
            )
        ]
    )
    _patch_handle(monkeypatch, handlers.query_info_cad, outcome)

    result = runner.invoke(app, ["query-info-cad"])
    assert result.exit_code == 0
    assert "company_classification" in result.stdout


def test_query_info_cad_command_detail_table(monkeypatch) -> None:
    """Query-info-cad com CNPJ deve renderizar tabela de detalhe."""
    outcome = Outcome.success(
        payload=[
            QueryInfoCadResult(
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
    _patch_handle(monkeypatch, handlers.query_info_cad, outcome)

    result = runner.invoke(app, ["query-info-cad", "--cnpj", "00.000.000/0001-91"])
    assert result.exit_code == 0
    assert "Classificação" in result.stdout
