"""Interactive setup: add providers and credentials to the config file.

Only identifiers and locations are asked for, never secret values. The wizard starts from an
empty prompt, keeps everything already in the file, and saves after each addition.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import questionary
import typer

from rotator import inventory


@dataclass(frozen=True)
class Field:
    name: str
    prompt: str
    default: str | None = None
    required: bool = False


@dataclass(frozen=True)
class Spec:
    mode: str
    settings: tuple[Field, ...] = ()
    ref: tuple[Field, ...] = ()
    has_kind: bool = False


GITHUB_KINDS = ("fine-grained", "classic")

SPECS: dict[str, Spec] = {
    "cloudflare": Spec(
        mode="auto",
        settings=(
            Field(
                "manager_token_env",
                "Env var holding the token that rolls tokens",
                "CLOUDFLARE_ROTATOR_TOKEN",
            ),
            Field("account_id", "Account id (blank for user-owned tokens)"),
        ),
        ref=(Field("token_id", "Cloudflare token id", required=True),),
    ),
    "jira-data-center": Spec(
        mode="auto",
        settings=(
            Field("base_url", "Jira base URL", required=True),
            Field("current_token_env", "Env var holding the current PAT", "JIRA_ROTATOR_TOKEN"),
        ),
    ),
    "github": Spec(mode="assisted", has_kind=True),
    "github-enterprise": Spec(
        mode="assisted",
        settings=(Field("host", "GitHub Enterprise host", required=True),),
        has_kind=True,
    ),
    "runpod": Spec(mode="assisted"),
}


def _ask(field: Field) -> str | None:
    default = field.default if field.default or field.required else ""
    value = typer.prompt(field.prompt, default=default, show_default=bool(field.default))
    return value.strip() or None


def _fields(fields: tuple[Field, ...]) -> dict[str, str]:
    answers = {f.name: _ask(f) for f in fields}
    return {name: value for name, value in answers.items() if value}


def _choose(prompt: str, options: list[str], default: str | None = None) -> str:
    """Arrow-key list on a terminal; typing one of the names otherwise (pipes, tests)."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        picked = questionary.select(prompt, choices=options, default=default).ask()
        if picked is None:
            raise typer.Abort()
        return picked
    while True:
        value = typer.prompt(f"{prompt} ({', '.join(options)})", default=default).strip()
        if value in options:
            return value
        typer.echo(f"  pick one of: {', '.join(options)}")


def _days(prompt: str, default: int) -> int:
    while True:
        value = typer.prompt(prompt, default=str(default)).strip()
        if value.isdecimal() and int(value) >= 1:
            return int(value)
        typer.echo("  enter a whole number of days, 1 or more")


def _new_id(prompt: str, taken: set[str], default: str | None = None) -> str:
    while True:
        value = typer.prompt(prompt, default=default).strip()
        if value and value not in taken:
            return value
        typer.echo(f"  {value!r} is empty or already used")


def _add_provider(data: dict[str, Any], path: Path) -> None:
    kind = _choose("Provider type", sorted(SPECS))
    taken = {p["id"] for p in data["providers"]} | set(inventory.PROVIDERS) - {kind}
    entry: dict[str, Any] = {
        "id": _new_id("Name for this provider (credentials refer to it)", taken, kind),
        "type": kind,
    }
    settings = _fields(SPECS[kind].settings)
    if settings:
        entry["settings"] = settings
    data["providers"].append(entry)
    inventory.save(path, data)
    typer.echo(f"  saved provider {entry['id']}")


NEW_ENV_FILE = "new"


def _env_file(known: list[str]) -> str:
    if known:
        picked = _choose("Env file", [*known, NEW_ENV_FILE], known[0])
        if picked != NEW_ENV_FILE:
            return picked
    return typer.prompt("Env file path (e.g. ~/projects/x/.envrc)")


def _add_destinations(data: dict[str, Any]) -> list[dict[str, str]]:
    known = list(dict.fromkeys(d["path"] for c in data["credentials"] for d in c["destinations"]))
    destinations = []
    while True:
        path = _env_file(known)
        destinations.append(
            {"type": "envfile", "path": path, "var": typer.prompt("Variable name in that file")}
        )
        known = [p for p in known if p != path]
        if not typer.confirm("Add another env file?", default=False):
            return destinations


def _add_credential(data: dict[str, Any], path: Path) -> None:
    providers = {p["id"]: p for p in data["providers"]}
    provider = providers[
        _choose(
            "Provider", sorted(providers), next(iter(providers)) if len(providers) == 1 else None
        )
    ]
    spec = SPECS[provider["type"]]
    entry: dict[str, Any] = {
        "id": _new_id(
            "Name for this credential (used as `rotate <name>`)",
            {c["id"] for c in data["credentials"]},
        ),
        "provider": provider["id"],
        "mode": spec.mode,
    }
    if spec.has_kind:
        entry["kind"] = _choose("Token kind", list(GITHUB_KINDS), GITHUB_KINDS[0])
    ref = _fields(spec.ref)
    if ref:
        entry["provider_ref"] = ref
    entry["store"] = {
        "type": "bitwarden",
        "item": typer.prompt("Bitwarden item name", default=entry["id"]),
    }
    entry["destinations"] = _add_destinations(data)
    entry["rotate_every_days"] = _days("Rotate every how many days", 90)
    data["credentials"].append(entry)
    inventory.save(path, data)
    typer.echo(f"  saved credential {entry['id']}")


def run(path: Path) -> None:
    data = inventory.read_raw(path)
    typer.echo(
        f"{path}: {len(data['providers'])} providers, {len(data['credentials'])} credentials kept"
    )
    while typer.confirm("Add a provider?", default=not data["providers"]):
        _add_provider(data, path)
    if not data["providers"]:
        typer.echo("Credentials need a provider; run --init again to add one.")
        return
    while typer.confirm("Add a credential?", default=not data["credentials"]):
        _add_credential(data, path)
    inventory.save(path, data)
    typer.echo(f"saved {path}")
