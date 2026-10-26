import json
import os
from pathlib import Path

import pytest

from conftest import ITEM
from rotator import destinations
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


def test_ensure_session_keeps_an_existing_session(vault):
    destinations.ensure_session(lambda prompt: pytest.fail("should not prompt"))


def test_ensure_session_unlocks_with_a_hidden_prompt_and_exports_the_session(
    vault, monkeypatch, tmp_path
):
    monkeypatch.delenv("BW_SESSION")
    prompts = []

    def read(prompt):
        prompts.append(prompt)
        return "correct-horse"

    destinations.ensure_session(read)
    assert os.environ["BW_SESSION"] == "session-key-from-unlock"
    assert "hidden" in prompts[0]
    assert "correct-horse" not in (tmp_path / "argv.log").read_text()
    monkeypatch.delenv("BW_SESSION")


def test_ensure_session_wrong_password(vault, monkeypatch):
    monkeypatch.delenv("BW_SESSION")
    with pytest.raises(DestinationError, match="Invalid master password") as e:
        destinations.ensure_session(lambda prompt: "wrong-password")
    assert "wrong-password" not in str(e.value)
    assert "BW_SESSION" not in os.environ


def test_ensure_session_requires_a_prior_login(vault, monkeypatch):
    monkeypatch.delenv("BW_SESSION")
    monkeypatch.setenv("FAKE_BW_STATUS", "unauthenticated")
    with pytest.raises(DestinationError, match="bw login --apikey"):
        destinations.ensure_session(lambda prompt: pytest.fail("should not prompt"))
