import os
import tempfile
from dataclasses import dataclass, field
from datetime import date
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
class ProviderConfig:
    """Settings shared by every credential that names this provider by id."""

    id: str
    type: str
    settings: dict[str, Any] = field(default_factory=dict)


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
    last_rotated: date | None = None


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


def _date(value: Any, where: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    elif type(value) is date:
        return value
    raise InventoryError(f"{where}: expected a date like 2026-10-26")


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


def _credential(raw: Any, index: int, provider_configs: dict[str, ProviderConfig]) -> Credential:
    cred_id = raw.get("id") if isinstance(raw, dict) else None
    where = f"credentials[{index}]" if cred_id is None else f"credential {cred_id}"
    data = _mapping(
        raw,
        where,
        {"id", "provider", "mode", "store", "destinations", "rotate_every_days"},
        {"provider_ref", "kind", "grace_days", "notes", "last_rotated"},
    )
    destinations = data["destinations"]
    if not isinstance(destinations, list) or not destinations:
        raise InventoryError(f"{where}.destinations: expected a non-empty list")
    provider_ref = data.get("provider_ref", {})
    if not isinstance(provider_ref, dict):
        raise InventoryError(f"{where}.provider_ref: expected a mapping")
    provider = _choice(data["provider"], f"{where}.provider", PROVIDERS | provider_configs.keys())
    if provider in provider_configs:
        configured = provider_configs[provider]
        provider = configured.type
        provider_ref = {**configured.settings, **provider_ref}
    return Credential(
        id=_text(data["id"], f"{where}.id"),
        provider=provider,
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
        last_rotated=_date(data.get("last_rotated"), f"{where}.last_rotated"),
    )


def _provider_config(raw: Any, index: int) -> ProviderConfig:
    where = f"providers[{index}]"
    data = _mapping(raw, where, {"id", "type"}, {"settings"})
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise InventoryError(f"{where}.settings: expected a mapping")
    config = ProviderConfig(
        id=_text(data["id"], f"{where}.id"),
        type=_choice(data["type"], f"{where}.type", PROVIDERS),
        settings=settings,
    )
    if config.id in PROVIDERS and config.id != config.type:
        raise InventoryError(f"{where}.id: {config.id!r} is a provider type; pick another id")
    return config


def _list(data: dict[str, Any], key: str, source: str) -> list[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise InventoryError(f"{source}: {key} must be a list")
    return value


def _unique(ids: list[str], what: str) -> None:
    for i, name in enumerate(ids):
        if name in ids[:i]:
            raise InventoryError(f"duplicate {what} id {name}")


def validate(raw: Any, source: str) -> list[Credential]:
    """Check a parsed config and return its credentials with provider settings applied."""
    data = _mapping(raw, source, {"credentials"}, {"providers"})
    provider_configs = [
        _provider_config(p, i) for i, p in enumerate(_list(data, "providers", source))
    ]
    _unique([p.id for p in provider_configs], "provider")
    by_id = {p.id: p for p in provider_configs}
    credentials = [
        _credential(c, i, by_id) for i, c in enumerate(_list(data, "credentials", source))
    ]
    _unique([c.id for c in credentials], "credential")
    return credentials


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except OSError as e:
        raise InventoryError(f"{path}: {e.strerror}") from e
    except yaml.YAMLError as e:
        raise InventoryError(f"{path}: invalid YAML") from e


def load(path: Path) -> list[Credential]:
    return validate(_read_yaml(path), str(path))


def read_raw(path: Path) -> dict[str, Any]:
    """The file's content for editing; an empty config when the file does not exist."""
    if not path.exists():
        return {"providers": [], "credentials": []}
    raw = _read_yaml(path)
    validate(raw, str(path))
    return {"providers": [], **raw}


def save(path: Path, data: dict[str, Any]) -> None:
    """Write a config atomically with mode 0600 once it validates."""
    validate(data, str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
