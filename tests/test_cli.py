from typer.testing import CliRunner

from security.cli import app

runner = CliRunner()


def test_root_lists_credentials():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "credentials" in result.output


def test_credentials_has_rotate_test_and_lint():
    result = runner.invoke(app, ["credentials", "--help"])
    assert result.exit_code == 0
    for command in ("rotate", "test", "lint"):
        assert command in result.output
    assert "rotator" not in result.output


def test_rotate_offers_check_and_due():
    result = runner.invoke(app, ["credentials", "rotate", "--help"])
    assert result.exit_code == 0
    for option in ("--check", "--due"):
        assert option in result.output


def test_root_test_and_lint_commands_exist():
    result = runner.invoke(app, ["--help"])
    assert "test" in result.output
    assert "lint" in result.output


def test_credentials_offers_init():
    result = runner.invoke(app, ["credentials", "--help"])
    assert "--init" in result.output


def test_credentials_without_arguments_shows_help():
    result = runner.invoke(app, ["credentials"])
    assert result.exit_code == 0
    assert "rotate" in result.output
