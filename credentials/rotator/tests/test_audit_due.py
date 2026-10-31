import json
from datetime import UTC, date, datetime

import pytest
import yaml
from typer.testing import CliRunner

from conftest import app
from rotator import due, inventory
from rotator.audit import AuditLog

runner = CliRunner()


def credential(id="c", days=30, last_rotated=None):
    return inventory.Credential(
        id=id,
        provider="p",
        mode="auto",
        store=inventory.Store(type="bitwarden", item="i"),
        destinations=[],
        rotate_every_days=days,
        last_rotated=last_rotated,
    )


def test_audit_appends_json_lines_privately(tmp_path):
    log = AuditLog(tmp_path / "audit.log")
    log.record("c", "cloudflare", "verify", "ok")
    log.record("c", "cloudflare", "rotated", "old credential revoked")
    lines = [json.loads(line) for line in (tmp_path / "audit.log").read_text().splitlines()]
    assert [e["step"] for e in lines] == ["verify", "rotated"]
    assert set(lines[0]) == {"ts", "credential", "provider", "step", "detail"}
    assert (tmp_path / "audit.log").stat().st_mode & 0o777 == 0o600


def test_last_rotated_only_counts_rotated_entries_for_that_credential(tmp_path):
    log = AuditLog(tmp_path / "audit.log")
    assert log.last_rotated("c") is None
    log.record("c", "p", "verify", "ok")
    log.record("other", "p", "rotated")
    assert log.last_rotated("c") is None
    log.record("c", "p", "rotated")
    assert log.last_rotated("c") is not None


def test_last_rotated_skips_corrupt_lines(tmp_path):
    path = tmp_path / "audit.log"
    path.write_text("not json\n")
    log = AuditLog(path)
    log.record("c", "p", "rotated")
    assert log.last_rotated("c") is not None


def test_due_statuses(tmp_path):
    today = date(2026, 10, 26)
    log = AuditLog(tmp_path / "audit.log")
    creds = [
        credential("overdue", 30, date(2026, 9, 1)),
        credential("soon", 30, date(2026, 10, 10)),
        credential("fine", 90, date(2026, 10, 20)),
        credential("never"),
    ]
    rows = {r.credential_id: r for r in due.report(creds, log, today, 14)}
    assert rows["overdue"].status == "overdue"
    assert rows["overdue"].days_left == -25
    assert (rows["soon"].status, rows["soon"].days_left) == ("due soon", 14)
    assert rows["fine"].status == "ok"
    assert rows["never"].status == "never rotated"


def test_due_prefers_the_latest_of_log_and_inventory(tmp_path):
    log = AuditLog(tmp_path / "audit.log")
    log.record("c", "p", "rotated")
    today = date.today()
    [row] = due.report([credential("c", 30, date(2020, 1, 1))], log, today, 14)
    assert row.status == "ok"


def write_inventory(tmp_path, *credentials):
    path = tmp_path / "inventory.yaml"
    path.write_text(yaml.safe_dump({"credentials": list(credentials)}))
    return path


def entry(id, days, last_rotated=None):
    e = {
        "id": id,
        "provider": "runpod",
        "mode": "assisted",
        "store": {"type": "bitwarden", "item": "i"},
        "destinations": [{"type": "envfile", "path": "/tmp/x", "var": "V"}],
        "rotate_every_days": days,
    }
    if last_rotated:
        e["last_rotated"] = last_rotated
    return e


def test_due_command_lists_and_flags_overdue(tmp_path):
    path = write_inventory(tmp_path, entry("old", 30, "2020-01-01"), entry("new", 30))
    result = runner.invoke(app, ["rotate", "--due", "--inventory", str(path)])
    assert result.exit_code == 1
    assert result.output.index("overdue") < result.output.index("never rotated")


def test_due_command_ok_exits_zero(tmp_path):
    today = datetime.now(UTC).date().isoformat()
    path = write_inventory(tmp_path, entry("fresh", 90, today))
    result = runner.invoke(app, ["rotate", "--due", "--inventory", str(path)])
    assert result.exit_code == 0
    assert "ok" in result.output


def test_audit_log_defaults_next_to_the_inventory_and_can_be_overridden(tmp_path, monkeypatch):
    from rotator.cli import _audit_log

    monkeypatch.delenv("ROTATOR_AUDIT_LOG", raising=False)
    assert _audit_log(tmp_path / "inventory.yaml").path == tmp_path / "audit.log"
    monkeypatch.setenv("ROTATOR_AUDIT_LOG", str(tmp_path / "elsewhere.log"))
    assert _audit_log(tmp_path / "inventory.yaml").path == tmp_path / "elsewhere.log"


def test_inventory_rejects_bad_last_rotated(tmp_path):
    path = write_inventory(tmp_path, entry("c", 30, "yesterday"))
    with pytest.raises(inventory.InventoryError, match="last_rotated"):
        inventory.load(path)
