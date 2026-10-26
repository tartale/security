import subprocess
import sys
from typing import Annotated

import typer

app = typer.Typer(help="Rotate API keys and tokens.", no_args_is_help=True)


def _run(*args: str) -> None:
    raise typer.Exit(subprocess.call([sys.executable, "-m", *args]))


@app.command(context_settings={"ignore_unknown_options": True})
def test(
    args: Annotated[list[str] | None, typer.Argument(help="Extra pytest arguments.")] = None,
) -> None:
    """Run the test suite."""
    _run("pytest", *(args or []))


@app.command()
def lint() -> None:
    """Check style and import order."""
    _run("ruff", "check", ".")
