import json
import stat
import sys
from pathlib import Path

import pytest

from rotator.destinations import Bitwarden, DestinationError

FAKE_BW = f"""#!{sys.executable}
import base64, json, os, sys

db = json.load(open(os.environ["FAKE_BW_DB"]))
with open(os.environ["FAKE_BW_ARGV"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
args = [a for a in sys.argv[1:] if a != "--nointeraction"]
if args[:2] == ["get", "item"]:
    item = next((i for i in db if i["name"] == args[2]), None)
    if item is None:
        sys.exit(print("Not found.", file=sys.stderr) or 1)
    print(json.dumps(item))
elif args[:2] == ["edit", "item"]:
    new = json.loads(base64.b64decode(sys.stdin.read()))
    assert new["id"] == args[2]
    db = [new if i["id"] == new["id"] else i for i in db]
    json.dump(db, open(os.environ["FAKE_BW_DB"], "w"))
    print(json.dumps(new))
else:
    sys.exit(2)
"""

ITEM = {
    "id": "abc-123",
    "name": "Cloudflare DNS token",
    "login": {"username": "me", "password": "old-secret"},
    "fields": [{"name": "keep", "value": "v", "type": 0}],
}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    bw = bindir / "bw"
    bw.write_text(FAKE_BW)
    bw.chmod(bw.stat().st_mode | stat.S_IEXEC)
    db = tmp_path / "db.json"
    db.write_text(json.dumps([ITEM]))
    monkeypatch.setenv("PATH", f"{bindir}:/usr/bin:/bin")
    monkeypatch.setenv("FAKE_BW_DB", str(db))
    monkeypatch.setenv("FAKE_BW_ARGV", str(tmp_path / "argv.log"))
    monkeypatch.setenv("BW_SESSION", "session")
    return db


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
