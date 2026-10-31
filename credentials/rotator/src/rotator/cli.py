import getpass
import os
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from rotator import destinations, due, flow, inventory, providers, wizard
from rotator.audit import AuditLog

PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_DIR.parent / "credentials.yaml"
InventoryOption = Annotated[
    Path, typer.Option("--inventory", envvar="ROTATOR_INVENTORY", help="Config file.")
]


def _load(path: Path) -> list[inventory.Credential]:
    try:
        return inventory.load(path)
    except inventory.InventoryError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e


def _check(path: Path) -> None:
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


def _audit_log(inventory_path: Path) -> AuditLog:
    default = inventory_path.resolve().parent / "audit.log"
    return AuditLog(Path(os.environ.get("ROTATOR_AUDIT_LOG", default)))


def _rotate_one(credential_id: str, path: Path, dry_run: bool, yes: bool) -> None:
    matches = [c for c in _load(path) if c.id == credential_id]
    if not matches:
        typer.echo(f"error: no credential {credential_id} in {path}", err=True)
        raise typer.Exit(1)
    credential = matches[0]
    audit = _audit_log(path)

    def report(step: str, detail: str) -> None:
        typer.echo(f"{step}: {detail}")
        audit.record(credential.id, credential.provider, step, detail)

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
        if any(isinstance(t.adapter, destinations.Bitwarden) for t in targets):
            destinations.ensure_session(getpass.getpass)
        outcome = flow.rotate(credential, provider, targets, TerminalPrompter(yes), report)
    except (flow.RotationError, destinations.DestinationError) as e:
        audit.record(credential.id, credential.provider, "failed", str(e))
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    if not outcome.old_revoked:
        audit.record(credential.id, credential.provider, "rotated", "old credential NOT revoked")
        raise typer.Exit(2)
    audit.record(credential.id, credential.provider, "rotated", "old credential revoked")
    typer.echo(f"{credential.id} rotated")


def _due(path: Path, within: int) -> None:
    credentials = _load(path)
    today = datetime.now(UTC).date()
    rows = due.report(credentials, _audit_log(path), today, within)
    for row in sorted(rows, key=lambda r: (r.days_left is None, r.days_left)):
        when = f"{row.due_on} ({row.days_left:+d}d)" if row.due_on else "-"
        typer.echo(f"{row.status:<14} {row.credential_id:<30} {when}")
    if any(r.status == "overdue" for r in rows):
        raise typer.Exit(1)


def rotate(
    credential_id: Annotated[
        str | None, typer.Argument(metavar="[ID]", help="Credential to rotate.")
    ] = None,
    check: Annotated[bool, typer.Option("--check", help="Validate the inventory file.")] = False,
    due_flag: Annotated[
        bool, typer.Option("--due", help="Show when each credential is due; exit 1 if overdue.")
    ] = False,
    within: Annotated[
        int, typer.Option(help="With --due: days ahead that count as due soon.")
    ] = 14,
    dry_run: Annotated[bool, typer.Option(help="Show the steps without doing any.")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Skip the overwrite confirmation.")] = False,
    path: InventoryOption = DEFAULT_CONFIG,
) -> None:
    """Rotate a credential (ID), or with --check / --due inspect the inventory."""
    if [credential_id is not None, check, due_flag].count(True) != 1:
        typer.echo("error: give exactly one of ID, --check or --due", err=True)
        raise typer.Exit(2)
    if check:
        _check(path)
    elif due_flag:
        _due(path, within)
    else:
        _rotate_one(credential_id, path, dry_run, yes)


def init() -> None:
    """Add providers and credentials to the config file, keeping what is already there."""
    try:
        wizard.run(Path(os.environ.get("ROTATOR_INVENTORY", DEFAULT_CONFIG)))
    except inventory.InventoryError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
