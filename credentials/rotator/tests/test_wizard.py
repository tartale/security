import stat
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from conftest import app
from rotator import inventory, providers, wizard

runner = CliRunner()

CLOUDFLARE_PROVIDER = ["y", "cloudflare", "", "", "", "n"]
CLOUDFLARE_CREDENTIAL = ["y", "", "cf-main", "abc123", "", "~/x/.envrc", "CF", "n", "", "n"]


def run_init(path, monkeypatch, answers):
    monkeypatch.setenv("ROTATOR_INVENTORY", str(path))
    return runner.invoke(app, ["init"], input="\n".join(answers) + "\n")


def test_first_run_builds_a_valid_private_config(tmp_path, monkeypatch):
    path = tmp_path / "credentials.yaml"
    result = run_init(path, monkeypatch, CLOUDFLARE_PROVIDER + CLOUDFLARE_CREDENTIAL)
    assert result.exit_code == 0, result.output
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    [credential] = inventory.load(path)
    assert (credential.id, credential.provider, credential.mode) == (
        "cf-main",
        "cloudflare",
        "auto",
    )
    assert credential.provider_ref == {
        "manager_token_env": "CLOUDFLARE_ROTATOR_TOKEN",
        "token_id": "abc123",
    }
    assert credential.store.item == "cf-main"
    assert credential.rotate_every_days == 90


def test_later_runs_keep_earlier_providers_and_credentials(tmp_path, monkeypatch):
    path = tmp_path / "credentials.yaml"
    run_init(path, monkeypatch, CLOUDFLARE_PROVIDER + CLOUDFLARE_CREDENTIAL)
    second = [
        "y",
        "runpod",
        "",
        "n",
        "y",
        "runpod",
        "rp",
        "",
        "new",
        "~/x/.env",
        "RP",
        "n",
        "30",
        "n",
    ]
    result = run_init(path, monkeypatch, second)
    assert result.exit_code == 0, result.output
    assert "1 providers, 1 credentials kept" in result.output
    data = yaml.safe_load(path.read_text())
    assert [p["id"] for p in data["providers"]] == ["cloudflare", "runpod"]
    assert [c["id"] for c in data["credentials"]] == ["cf-main", "rp"]
    assert data["credentials"][1]["rotate_every_days"] == 30


def test_declining_everything_changes_nothing(tmp_path, monkeypatch):
    path = tmp_path / "credentials.yaml"
    run_init(path, monkeypatch, CLOUDFLARE_PROVIDER + CLOUDFLARE_CREDENTIAL)
    before = path.read_text()
    result = run_init(path, monkeypatch, ["n", "n"])
    assert result.exit_code == 0, result.output
    assert path.read_text() == before


def test_taken_ids_and_bad_numbers_are_asked_again(tmp_path, monkeypatch):
    path = tmp_path / "credentials.yaml"
    run_init(path, monkeypatch, CLOUDFLARE_PROVIDER + CLOUDFLARE_CREDENTIAL)
    answers = [
        "n",
        "y",
        "",
        "cf-main",
        "cf-two",
        "abc",
        "",
        "~/x/.envrc",
        "CF",
        "n",
        "soon",
        "0",
        "7",
        "n",
    ]
    result = run_init(path, monkeypatch, answers)
    assert result.exit_code == 0, result.output
    assert "already used" in result.output
    assert result.output.count("enter a whole number") == 2
    assert [c.id for c in inventory.load(path)] == ["cf-main", "cf-two"]
    assert inventory.load(path)[1].rotate_every_days == 7


def test_an_invalid_existing_file_is_reported_and_left_alone(tmp_path, monkeypatch):
    path = tmp_path / "credentials.yaml"
    path.write_text("credentials: nope\n")
    result = run_init(path, monkeypatch, ["y"])
    assert result.exit_code == 1
    assert "credentials must be a list" in result.output
    assert path.read_text() == "credentials: nope\n"


@pytest.mark.parametrize("kind", sorted(wizard.SPECS))
def test_every_wizard_provider_builds_a_working_adapter(kind):
    spec = wizard.SPECS[kind]
    required = lambda fields: {f.name: "x.example.com" for f in fields if f.required}  # noqa: E731
    credential = {
        "id": "c",
        "provider": "p",
        "mode": spec.mode,
        "store": {"type": "bitwarden", "item": "i"},
        "destinations": [{"type": "envfile", "path": "~/.env", "var": "V"}],
        "rotate_every_days": 30,
        "provider_ref": required(spec.ref),
    }
    if spec.has_kind:
        credential["kind"] = wizard.GITHUB_KINDS[0]
    config = {
        "providers": [{"id": "p", "type": kind, "settings": required(spec.settings)}],
        "credentials": [credential],
    }
    env = {"CLOUDFLARE_ROTATOR_TOKEN": "t", "JIRA_ROTATOR_TOKEN": "t"}
    [loaded] = inventory.validate(config, "test")
    assert providers.for_credential(loaded, env).capability == spec.mode


def test_an_existing_env_file_can_be_picked_again(tmp_path, monkeypatch):
    path = tmp_path / "credentials.yaml"
    run_init(path, monkeypatch, CLOUDFLARE_PROVIDER + CLOUDFLARE_CREDENTIAL)
    answers = ["n", "y", "", "cf-two", "abc", "", "~/x/.envrc", "CF2", "n", "", "n"]
    result = run_init(path, monkeypatch, answers)
    assert "Env file (~/x/.envrc, new)" in result.output
    assert [d.path for c in inventory.load(path) for d in c.destinations] == [
        Path("~/x/.envrc").expanduser()
    ] * 2


def terminal(monkeypatch, answer):
    asked = {}

    class Question:
        def ask(self):
            return answer

    def select(prompt, choices, default):
        asked.update(prompt=prompt, choices=choices, default=default)
        return Question()

    monkeypatch.setattr(wizard.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(wizard.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(wizard.questionary, "select", select)
    return asked


def test_terminal_choices_use_an_arrow_key_list(monkeypatch):
    asked = terminal(monkeypatch, "classic")
    assert wizard._choose("Token kind", ["fine-grained", "classic"], "fine-grained") == "classic"
    assert asked == {
        "prompt": "Token kind",
        "choices": ["fine-grained", "classic"],
        "default": "fine-grained",
    }


def test_cancelling_the_list_aborts(monkeypatch):
    terminal(monkeypatch, None)
    with pytest.raises(wizard.typer.Abort):
        wizard._choose("Provider", ["a", "b"])
