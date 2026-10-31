import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rotator.cli import PROJECT_DIR as ROTATOR_DIR
from rotator.cli import init, rotate

ROOT = Path(__file__).resolve().parents[2]
CREDENTIAL_PROJECTS = [ROTATOR_DIR]
PROJECTS = [ROOT, *CREDENTIAL_PROJECTS]

app = typer.Typer(help="Security projects.", no_args_is_help=True)
credentials = typer.Typer(help="Credential management.")

app.add_typer(credentials, name="credentials")
credentials.command("rotate")(rotate)


@credentials.callback(invoke_without_command=True)
def credentials_root(
    ctx: typer.Context,
    init_config: Annotated[
        bool, typer.Option("--init", help="Add providers and credentials interactively.")
    ] = False,
) -> None:
    if init_config:
        init()
    elif ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _run_all(projects: list[Path], *args: str) -> None:
    failed = False
    for project in projects:
        typer.echo(f"== {project.relative_to(ROOT)}")
        if subprocess.call([sys.executable, "-m", *args], cwd=project):
            failed = True
    raise typer.Exit(1 if failed else 0)


PytestArgs = Annotated[list[str] | None, typer.Argument(help="Extra pytest arguments.")]
UNKNOWN_OPTIONS = {"ignore_unknown_options": True}


@app.command("test", context_settings=UNKNOWN_OPTIONS)
def test_all(args: PytestArgs = None) -> None:
    """Run every project's test suite."""
    _run_all(PROJECTS, "pytest", *(args or []))


@app.command("lint")
def lint_all() -> None:
    """Lint every project."""
    _run_all(PROJECTS, "ruff", "check", ".")


@credentials.command("test", context_settings=UNKNOWN_OPTIONS)
def test_credentials(args: PytestArgs = None) -> None:
    """Run the credentials projects' test suites."""
    _run_all(CREDENTIAL_PROJECTS, "pytest", *(args or []))


@credentials.command("lint")
def lint_credentials() -> None:
    """Lint the credentials projects."""
    _run_all(CREDENTIAL_PROJECTS, "ruff", "check", ".")
