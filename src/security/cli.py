import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rotator.cli import PROJECT_DIR as ROTATOR_DIR
from rotator.cli import app as rotator_app

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = [ROOT, ROTATOR_DIR]

app = typer.Typer(help="Security projects.", no_args_is_help=True)
credentials = typer.Typer(help="Credential management.", no_args_is_help=True)

app.add_typer(credentials, name="credentials")
credentials.add_typer(rotator_app, name="rotator")


def _run_all(*args: str) -> None:
    failed = False
    for project in PROJECTS:
        typer.echo(f"== {project.relative_to(ROOT)}")
        if subprocess.call([sys.executable, "-m", *args], cwd=project):
            failed = True
    raise typer.Exit(1 if failed else 0)


@app.command(context_settings={"ignore_unknown_options": True})
def test(
    args: Annotated[list[str] | None, typer.Argument(help="Extra pytest arguments.")] = None,
) -> None:
    """Run every project's test suite."""
    _run_all("pytest", *(args or []))


@app.command()
def lint() -> None:
    """Lint every project."""
    _run_all("ruff", "check", ".")
