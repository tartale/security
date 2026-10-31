import json
import stat
import sys

import pytest
import typer

from rotator.cli import init, rotate

# A group (not a lone command) so tests invoke `rotate ...` as the root CLI does.
app = typer.Typer()
app.callback()(lambda: None)
app.command()(rotate)
app.command("init")(init)

FAKE_BW = f"""#!{sys.executable}
import base64, json, os, sys

db = json.load(open(os.environ["FAKE_BW_DB"]))
with open(os.environ["FAKE_BW_ARGV"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
args = [a for a in sys.argv[1:] if a != "--nointeraction"]
if args == ["status"]:
    print(json.dumps({{"status": os.environ.get("FAKE_BW_STATUS", "locked")}}))
elif args[:1] == ["unlock"]:
    assert args[1] == "--passwordenv" and args[3:] == ["--raw"]
    if os.environ.get(args[2]) != os.environ["FAKE_BW_PASSWORD"]:
        sys.exit(print("Invalid master password.", file=sys.stderr) or 1)
    print("session-key-from-unlock")
elif args[:2] == ["get", "item"]:
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
    monkeypatch.setenv("FAKE_BW_PASSWORD", "correct-horse")
    return db
