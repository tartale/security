import json

import httpx
import pytest
import respx

from rotator import inventory, providers
from rotator.providers import JiraDataCenter, ProviderError

BASE = "https://jira.example.com"


def credential(**ref):
    return inventory.Credential(
        id="jira-dc-personal",
        provider="jira-data-center",
        mode="auto",
        store=inventory.Store(type="bitwarden", item="i"),
        destinations=[],
        rotate_every_days=60,
        grace_days=3,
        provider_ref={"base_url": BASE, **ref},
    )


ENV = {"JIRA_ROTATOR_TOKEN": "current-pat"}


@respx.mock
def test_create_posts_name_and_expiry_with_current_pat():
    route = respx.post(f"{BASE}/rest/pat/latest/tokens").mock(
        return_value=httpx.Response(201, json={"id": 7, "rawToken": "brand-new-pat"})
    )
    jira = JiraDataCenter.from_credential(credential(), ENV)
    assert jira.create() == "brand-new-pat"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer current-pat"
    assert json.loads(request.content) == {"name": "jira-dc-personal", "expirationDuration": 77}


@respx.mock
def test_create_without_raw_token_is_an_error():
    respx.post(f"{BASE}/rest/pat/latest/tokens").mock(
        return_value=httpx.Response(200, json={"id": 7})
    )
    with pytest.raises(ProviderError, match="no rawToken"):
        JiraDataCenter.from_credential(credential(), ENV).create()


@respx.mock
def test_create_failure_reports_status_not_secrets():
    respx.post(f"{BASE}/rest/pat/latest/tokens").mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderError, match="401") as e:
        JiraDataCenter.from_credential(credential(), ENV).create()
    assert "current-pat" not in str(e.value)


@respx.mock
def test_verify_uses_the_new_pat():
    route = respx.get(f"{BASE}/rest/api/2/myself").mock(
        return_value=httpx.Response(200, json={"name": "me"})
    )
    JiraDataCenter.from_credential(credential(), ENV).verify("brand-new-pat")
    assert route.calls.last.request.headers["Authorization"] == "Bearer brand-new-pat"


@respx.mock
def test_verify_rejects_a_bad_pat():
    respx.get(f"{BASE}/rest/api/2/myself").mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderError, match="401"):
        JiraDataCenter.from_credential(credential(), ENV).verify("bad")


@respx.mock
def test_network_failure_is_a_clean_error():
    respx.get(f"{BASE}/rest/api/2/myself").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(ProviderError, match="ConnectError"):
        JiraDataCenter.from_credential(credential(), ENV).verify("x")


def test_ref_overrides():
    jira = JiraDataCenter.from_credential(
        credential(
            token_name="custom",
            expiration_days=30,
            current_token_env="MY_PAT",
            base_url=BASE + "/",
        ),
        {"MY_PAT": "p"},
    )
    assert (jira.base_url, jira.token_name, jira.expiration_days) == (BASE, "custom", 30)


@pytest.mark.parametrize(
    ("ref", "environ", "message"),
    [
        ({"base_url": ""}, ENV, "missing base_url"),
        ({"nope": 1}, ENV, "unknown field nope"),
        ({}, {}, "JIRA_ROTATOR_TOKEN is not set"),
        ({"expiration_days": "90"}, ENV, "expiration_days must be an integer"),
    ],
)
def test_from_credential_validates(ref, environ, message):
    with pytest.raises(ProviderError, match=message):
        JiraDataCenter.from_credential(credential(**ref), environ)


def test_factory_builds_jira():
    jira = providers.for_credential(credential(), ENV)
    assert isinstance(jira, JiraDataCenter)
    assert not jira.rolls_in_place
