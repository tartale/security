import json

import httpx
import respx
import yaml
from typer.testing import CliRunner

from conftest import ITEM
from rotator.cli import app

API = "https://api.cloudflare.com/client/v4"
TOKEN_ID = "ed17574386854bf78a67040be0a770b0"
runner = CliRunner()


def inventory_file(tmp_path, env_path):
    path = tmp_path / "inventory.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "credentials": [
                    {
                        "id": "cf",
                        "provider": "cloudflare",
                        "mode": "auto",
                        "provider_ref": {"token_id": TOKEN_ID},
                        "store": {"type": "bitwarden", "item": ITEM["name"]},
                        "destinations": [{"type": "envfile", "path": str(env_path), "var": "CF"}],
                        "rotate_every_days": 90,
                    }
                ]
            }
        )
    )
    return path


def ok(result):
    return httpx.Response(200, json={"success": True, "errors": [], "result": result})


@respx.mock
def test_rotate_end_to_end_with_real_adapters(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ROTATOR_TOKEN", "manager")
    env = tmp_path / ".envrc"
    env.write_text("export CF=old\nOTHER=1\n")
    respx.put(f"{API}/user/tokens/{TOKEN_ID}/value").mock(return_value=ok("rolled-secret"))
    respx.get(f"{API}/user/tokens/verify").mock(
        return_value=ok({"id": TOKEN_ID, "status": "active"})
    )
    result = runner.invoke(
        app, ["rotate", "cf", "--yes", "--inventory", str(inventory_file(tmp_path, env))]
    )
    assert result.exit_code == 0, result.output
    assert env.read_text() == "export CF=rolled-secret\nOTHER=1\n"
    assert json.loads(vault.read_text())[0]["login"]["password"] == "rolled-secret"
    assert "rolled-secret" not in result.output
    assert "cf rotated" in result.output
    audit = (tmp_path / "audit.log").read_text()
    assert '"step": "rotated"' in audit
    assert "rolled-secret" not in audit


@respx.mock
def test_failed_verification_leaves_everything_untouched(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ROTATOR_TOKEN", "manager")
    env = tmp_path / ".env"
    env.write_text("CF=old\n")
    respx.put(f"{API}/user/tokens/{TOKEN_ID}/value").mock(return_value=ok("rolled-secret"))
    respx.get(f"{API}/user/tokens/verify").mock(
        return_value=ok({"id": TOKEN_ID, "status": "disabled"})
    )
    result = runner.invoke(
        app, ["rotate", "cf", "--yes", "--inventory", str(inventory_file(tmp_path, env))]
    )
    assert result.exit_code == 1
    assert env.read_text() == "CF=old\n"
    assert "rolled-secret" not in result.output
    audit = (tmp_path / "audit.log").read_text()
    assert '"step": "failed"' in audit
    assert '"step": "rotated"' not in audit


@respx.mock
def test_dry_run_prints_the_plan_and_calls_nothing(tmp_path):
    result = runner.invoke(
        app,
        [
            "rotate",
            "cf",
            "--dry-run",
            "--inventory",
            str(inventory_file(tmp_path, tmp_path / ".env")),
        ],
        env={"CLOUDFLARE_ROTATOR_TOKEN": "manager"},
    )
    assert result.exit_code == 0, result.output
    assert "1. create new credential" in result.output
    assert "write to bitwarden Cloudflare DNS token" in result.output
    assert not respx.calls


def test_unknown_credential_id(tmp_path):
    result = runner.invoke(
        app, ["rotate", "nope", "--inventory", str(inventory_file(tmp_path, tmp_path / ".env"))]
    )
    assert result.exit_code == 1
    assert "no credential nope" in result.output


def test_missing_manager_token_is_a_clean_error(tmp_path):
    result = runner.invoke(
        app,
        [
            "rotate",
            "cf",
            "--dry-run",
            "--inventory",
            str(inventory_file(tmp_path, tmp_path / ".env")),
        ],
        env={"CLOUDFLARE_ROTATOR_TOKEN": ""},
    )
    assert result.exit_code == 1
    assert "CLOUDFLARE_ROTATOR_TOKEN is not set" in result.output
