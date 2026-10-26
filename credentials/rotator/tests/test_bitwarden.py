import json
from pathlib import Path

import pytest

from conftest import ITEM
from rotator.destinations import Bitwarden, DestinationError


def stored(db: Path) -> dict:
    return json.loads(db.read_text())[0]


def test_writes_login_password_without_argv_leak(vault, tmp_path):
    Bitwarden("Cloudflare DNS token").write("new-secret")
    item = stored(vault)
    assert item["login"] == {"username": "me", "password": "new-secret"}
    assert item["fields"] == ITEM["fields"]
    assert "new-secret" not in (tmp_path / "argv.log").read_text()


def test_writes_existing_custom_field(vault):
    item = dict(ITEM, fields=[{"name": "api", "value": "old", "type": 1}])
    vault.write_text(json.dumps([item]))
    Bitwarden("Cloudflare DNS token", "api").write("new")
    assert stored(vault)["fields"] == [{"name": "api", "value": "new", "type": 1}]
    assert stored(vault)["login"]["password"] == "old-secret"


def test_adds_missing_custom_field_as_hidden(vault):
    Bitwarden("Cloudflare DNS token", "api").write("new")
    assert stored(vault)["fields"][-1] == {
        "name": "api",
        "value": "new",
        "type": 1,
        "linkedId": None,
    }


def test_restore_puts_back_previous_item(vault):
    adapter = Bitwarden("Cloudflare DNS token")
    backup = adapter.read_current()
    adapter.write("new-secret")
    adapter.restore(backup)
    assert stored(vault) == ITEM


def test_backup_repr_hides_item(vault):
    assert "old-secret" not in repr(Bitwarden("Cloudflare DNS token").read_current())


def test_missing_item_is_a_clean_error(vault):
    with pytest.raises(DestinationError, match="Not found"):
        Bitwarden("nope").write("x")


def test_requires_session(vault, monkeypatch):
    monkeypatch.delenv("BW_SESSION")
    with pytest.raises(DestinationError, match="BW_SESSION"):
        Bitwarden("Cloudflare DNS token").read_current()


def test_requires_bw_binary(vault, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(DestinationError, match="bw not found"):
        Bitwarden("Cloudflare DNS token").read_current()


def test_item_without_login_cannot_hold_password(vault):
    vault.write_text(json.dumps([{"id": "abc-123", "name": "Cloudflare DNS token"}]))
    with pytest.raises(DestinationError, match="no login"):
        Bitwarden("Cloudflare DNS token").write("x")
