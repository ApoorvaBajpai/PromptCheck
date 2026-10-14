from typer.testing import CliRunner

from promptcheck_cli.main import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "PromptCheck CLI" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "PromptCheck CLI" in result.stdout
    assert "ping" in result.stdout
    assert "version" in result.stdout
