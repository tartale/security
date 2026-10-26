from typer.testing import CliRunner

from security.cli import app

runner = CliRunner()


def test_root_lists_credentials():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "credentials" in result.output


def test_credentials_lists_rotator():
    result = runner.invoke(app, ["credentials", "--help"])
    assert result.exit_code == 0
    assert "rotator" in result.output


def test_rotator_commands_are_mounted():
    result = runner.invoke(app, ["credentials", "rotator", "--help"])
    assert result.exit_code == 0
    for command in ("check", "lint", "test"):
        assert command in result.output


def test_test_and_lint_commands_exist():
    result = runner.invoke(app, ["--help"])
    assert "test" in result.output
    assert "lint" in result.output
