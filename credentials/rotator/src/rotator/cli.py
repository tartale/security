import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from rotator import inventory

app = typer.Typer(help="Rotate API keys and tokens.", no_args_is_help=True)


PROJECT_DIR = Path(__file__).resolve().parents[2]


def _run(*args: str) -> None:
    raise typer.Exit(subprocess.call([sys.executable, "-m", *args], cwd=PROJECT_DIR))


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


@app.command()
def check(
    path: Annotated[
        Path, typer.Option("--inventory", envvar="ROTATOR_INVENTORY", help="Inventory file.")
    ] = Path("inventory.yaml"),
) -> None:
    """Validate the inventory file."""
    try:
        credentials = inventory.load(path)
    except inventory.InventoryError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(f"{len(credentials)} credentials ok")
