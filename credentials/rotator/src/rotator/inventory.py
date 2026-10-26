from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROVIDERS = {
    "cloudflare",
    "jira-data-center",
    "github",
    "github-enterprise",
    "runpod",
    "modal",
    "bitwarden",
}
MODES = {"auto", "assisted"}
STORE_TYPES = {"bitwarden"}
DESTINATION_TYPES = {"envfile"}


class InventoryError(Exception):
    pass


@dataclass(frozen=True)
class Store:
    type: str
    item: str
    field: str = "password"


@dataclass(frozen=True)
class Destination:
    type: str
    path: Path
    var: str


@dataclass(frozen=True)
class Credential:
    id: str
    provider: str
    mode: str
    store: Store
    destinations: list[Destination]
    rotate_every_days: int
    provider_ref: dict[str, Any] = field(default_factory=dict)
    kind: str | None = None
    grace_days: int = 0
    notes: str | None = None


def _mapping(value: Any, where: str, required: set[str], optional: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InventoryError(f"{where}: expected a mapping")
    missing = required - value.keys()
    if missing:
        raise InventoryError(f"{where}: missing {', '.join(sorted(missing))}")
    unknown = value.keys() - required - optional
    if unknown:
        raise InventoryError(f"{where}: unknown field {', '.join(sorted(map(str, unknown)))}")
    return value


def _choice(value: Any, where: str, allowed: set[str]) -> str:
    if value not in allowed:
        raise InventoryError(f"{where}: {value!r} is not one of {', '.join(sorted(allowed))}")
    return value


def _days(value: Any, where: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InventoryError(f"{where}: expected an integer >= {minimum}")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise InventoryError(f"{where}: expected a non-empty string")
    return value


def _store(raw: Any, where: str) -> Store:
    data = _mapping(raw, where, {"type", "item"}, {"field"})
    return Store(
        type=_choice(data["type"], f"{where}.type", STORE_TYPES),
        item=_text(data["item"], f"{where}.item"),
        field=_text(data.get("field", "password"), f"{where}.field"),
    )


def _destination(raw: Any, where: str) -> Destination:
    data = _mapping(raw, where, {"type", "path", "var"}, set())
    return Destination(
        type=_choice(data["type"], f"{where}.type", DESTINATION_TYPES),
        path=Path(_text(data["path"], f"{where}.path")).expanduser(),
        var=_text(data["var"], f"{where}.var"),
    )


def _credential(raw: Any, index: int) -> Credential:
    cred_id = raw.get("id") if isinstance(raw, dict) else None
    where = f"credentials[{index}]" if cred_id is None else f"credential {cred_id}"
    data = _mapping(
        raw,
        where,
        {"id", "provider", "mode", "store", "destinations", "rotate_every_days"},
        {"provider_ref", "kind", "grace_days", "notes"},
    )
    destinations = data["destinations"]
    if not isinstance(destinations, list) or not destinations:
        raise InventoryError(f"{where}.destinations: expected a non-empty list")
    provider_ref = data.get("provider_ref", {})
    if not isinstance(provider_ref, dict):
        raise InventoryError(f"{where}.provider_ref: expected a mapping")
    return Credential(
        id=_text(data["id"], f"{where}.id"),
        provider=_choice(data["provider"], f"{where}.provider", PROVIDERS),
        mode=_choice(data["mode"], f"{where}.mode", MODES),
        store=_store(data["store"], f"{where}.store"),
        destinations=[
            _destination(d, f"{where}.destinations[{i}]") for i, d in enumerate(destinations)
        ],
        rotate_every_days=_days(data["rotate_every_days"], f"{where}.rotate_every_days", 1),
        provider_ref=provider_ref,
        kind=data.get("kind"),
        grace_days=_days(data.get("grace_days", 0), f"{where}.grace_days", 0),
        notes=data.get("notes"),
    )


def load(path: Path) -> list[Credential]:
    try:
        raw = yaml.safe_load(path.read_text())
    except OSError as e:
        raise InventoryError(f"{path}: {e.strerror}") from e
    except yaml.YAMLError as e:
        raise InventoryError(f"{path}: invalid YAML") from e
    data = _mapping(raw, str(path), {"credentials"}, set())
    if not isinstance(data["credentials"], list):
        raise InventoryError(f"{path}: credentials must be a list")
    credentials = [_credential(c, i) for i, c in enumerate(data["credentials"])]
    seen: set[str] = set()
    for c in credentials:
        if c.id in seen:
            raise InventoryError(f"duplicate credential id {c.id}")
        seen.add(c.id)
    return credentials
