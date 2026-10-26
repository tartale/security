import getpass
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Annotated

import typer

from rotator import flow, inventory, providers

PROJECT_DIR = Path(__file__).resolve().parents[2]
InventoryOption = Annotated[
    Path, typer.Option("--inventory", envvar="ROTATOR_INVENTORY", help="Inventory file.")
]

app = typer.Typer(help="Rotate API keys and tokens.", no_args_is_help=True)


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


def _load(path: Path) -> list[inventory.Credential]:
    try:
        return inventory.load(path)
    except inventory.InventoryError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def check(path: InventoryOption = Path("inventory.yaml")) -> None:
    """Validate the inventory file."""
    typer.echo(f"{len(_load(path))} credentials ok")


class TerminalPrompter:
    def __init__(self, assume_yes: bool) -> None:
        self.assume_yes = assume_yes

    def open_url(self, url: str) -> None:
        typer.echo(f"  {url}")
        webbrowser.open(url)

    def read_secret(self, prompt: str) -> str:
        return getpass.getpass(prompt)

    def confirm(self, message: str) -> bool:
        return self.assume_yes or typer.confirm(message)

    def acknowledge(self, message: str) -> bool:
        return typer.confirm(message)


def _report(step: str, detail: str) -> None:
    typer.echo(f"{step}: {detail}")


@app.command()
def rotate(
    credential_id: Annotated[str, typer.Argument(metavar="ID", help="Credential id.")],
    path: InventoryOption = Path("inventory.yaml"),
    dry_run: Annotated[bool, typer.Option(help="Show the steps without doing any.")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Skip the overwrite confirmation.")] = False,
) -> None:
    """Rotate one credential and distribute the new value."""
    matches = [c for c in _load(path) if c.id == credential_id]
    if not matches:
        typer.echo(f"error: no credential {credential_id} in {path}", err=True)
        raise typer.Exit(1)
    credential = matches[0]
    try:
        provider = providers.for_credential(credential, os.environ)
        targets = flow.targets_for(credential)
    except providers.ProviderError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    if dry_run:
        for i, step in enumerate(flow.plan(provider, targets), 1):
            typer.echo(f"{i}. {step}")
        return
    try:
        outcome = flow.rotate(credential, provider, targets, TerminalPrompter(yes), _report)
    except flow.RotationError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    if not outcome.old_revoked:
        raise typer.Exit(2)
    typer.echo(f"{credential.id} rotated")
