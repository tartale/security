from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from rotator import inventory
from rotator.cli import app

EXAMPLE = Path(__file__).parent.parent / "inventory.example.yaml"


def valid() -> dict:
    return yaml.safe_load(EXAMPLE.read_text())["credentials"][0]


def write(tmp_path: Path, *credentials: dict) -> Path:
    path = tmp_path / "inventory.yaml"
    path.write_text(yaml.safe_dump({"credentials": list(credentials)}))
    return path


def test_example_inventory_loads():
    credentials = inventory.load(EXAMPLE)
    assert [c.id for c in credentials] == [
        "cloudflare-dns-edit",
        "jira-dc-personal",
        "github-fine-grained-ci",
        "runpod-main",
    ]
    assert credentials[0].store.field == "password"
    assert credentials[0].destinations[0].path == Path("~/projects/example/.envrc").expanduser()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"mode": "manual"}, "mode"),
        ({"provider": "nope"}, "provider"),
        ({"rotate_every_days": 0}, "rotate_every_days"),
        ({"rotate_every_days": True}, "rotate_every_days"),
        ({"destinations": []}, "destinations"),
        ({"password": "hunter2"}, "unknown field password"),
        ({"store": {"type": "bitwarden"}}, "missing item"),
        ({"destinations": [{"type": "envfile", "path": "x"}]}, "missing var"),
    ],
)
def test_invalid_credential_names_the_problem(tmp_path, change, message):
    path = write(tmp_path, {**valid(), **change})
    with pytest.raises(inventory.InventoryError, match=message):
        inventory.load(path)


def test_duplicate_ids_rejected(tmp_path):
    path = write(tmp_path, valid(), valid())
    with pytest.raises(inventory.InventoryError, match="duplicate credential id"):
        inventory.load(path)


def test_missing_file_and_bad_yaml(tmp_path):
    with pytest.raises(inventory.InventoryError):
        inventory.load(tmp_path / "absent.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("credentials: [")
    with pytest.raises(inventory.InventoryError, match="invalid YAML"):
        inventory.load(bad)


def test_check_command(tmp_path):
    runner = CliRunner()
    ok = runner.invoke(app, ["check", "--inventory", str(EXAMPLE)])
    assert ok.exit_code == 0
    assert "4 credentials ok" in ok.output
    bad = runner.invoke(app, ["check", "--inventory", str(write(tmp_path, {"id": "x"}))])
    assert bad.exit_code == 1
