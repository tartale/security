from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from rotator import inventory, providers
from rotator.providers import ProviderError, RunPod


def credential(provider="github", kind="fine-grained", mode="assisted", **ref):
    return inventory.Credential(
        id="github-ci",
        provider=provider,
        mode=mode,
        store=inventory.Store(type="bitwarden", item="i"),
        destinations=[],
        rotate_every_days=30,
        grace_days=2,
        provider_ref=ref,
        kind=kind,
    )


def test_fine_grained_console_url_prefills_name_and_expiry():
    url = urlparse(providers.for_credential(credential(), {}).console_url())
    assert (url.netloc, url.path) == ("github.com", "/settings/personal-access-tokens/new")
    assert parse_qs(url.query) == {"name": ["github-ci"], "expires_in": ["46"]}


def test_expiry_is_capped_and_name_truncated():
    cred = credential(token_name="n" * 60)
    cred = inventory.Credential(**{**cred.__dict__, "rotate_every_days": 400})
    url = urlparse(providers.for_credential(cred, {}).console_url())
    assert parse_qs(url.query) == {"name": ["n" * 40], "expires_in": ["366"]}


def test_classic_urls():
    gh = providers.for_credential(credential(kind="classic"), {})
    assert gh.console_url() == "https://github.com/settings/tokens/new"
    assert gh.revoke_url() == "https://github.com/settings/tokens"


def test_fine_grained_revoke_url():
    gh = providers.for_credential(credential(), {})
    assert gh.revoke_url() == "https://github.com/settings/personal-access-tokens"


@respx.mock
def test_github_verify_calls_user_with_the_new_token():
    route = respx.get("https://api.github.com/user").mock(return_value=httpx.Response(200, json={}))
    providers.for_credential(credential(), {}).verify("ghp_new")
    assert route.calls.last.request.headers["Authorization"] == "Bearer ghp_new"


@respx.mock
def test_github_enterprise_uses_the_instance_api_and_console():
    route = respx.get("https://ghe.example.com/api/v3/user").mock(
        return_value=httpx.Response(200, json={})
    )
    gh = providers.for_credential(
        credential("github-enterprise", host="ghe.example.com"), {}
    )
    gh.verify("t")
    assert route.called
    assert gh.revoke_url() == "https://ghe.example.com/settings/personal-access-tokens"


@respx.mock
def test_github_verify_failure_reports_status_not_token():
    respx.get("https://api.github.com/user").mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderError, match="401") as e:
        providers.for_credential(credential(), {}).verify("ghp_secret")
    assert "ghp_secret" not in str(e.value)


@pytest.mark.parametrize(
    ("cred", "message"),
    [
        (credential(kind=None), "needs kind"),
        (credential(kind="other"), "needs kind"),
        (credential(nope=1), "unknown field nope"),
        (credential("github-enterprise"), "needs provider_ref.host"),
        (credential("github-enterprise", host="github.com"), "use provider github"),
        (credential(mode="auto"), "is assisted, inventory says mode: auto"),
    ],
)
def test_github_credential_validation(cred, message):
    with pytest.raises(ProviderError, match=message):
        providers.for_credential(cred, {})


@respx.mock
def test_runpod_verify_lists_pods_with_the_new_key():
    route = respx.get("https://rest.runpod.io/v1/pods").mock(
        return_value=httpx.Response(200, json=[])
    )
    runpod = providers.for_credential(credential("runpod", kind=None), {})
    assert isinstance(runpod, RunPod)
    runpod.verify("rp_new")
    assert route.calls.last.request.headers["Authorization"] == "Bearer rp_new"
    assert runpod.console_url() == runpod.revoke_url()


@respx.mock
def test_runpod_verify_rejects_bad_key():
    respx.get("https://rest.runpod.io/v1/pods").mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderError, match="401"):
        RunPod().verify("bad")


def test_cloudflare_has_nothing_to_revoke():
    cf = providers.Cloudflare.from_ref({"token_id": "t"}, {"CLOUDFLARE_ROTATOR_TOKEN": "m"})
    assert cf.revoke_url() is None


def test_jira_revoke_url_is_the_profile_page():
    jira = providers.JiraDataCenter("https://jira.example.com", "n", 30, "pat")
    assert jira.revoke_url() == "https://jira.example.com/secure/ViewProfile.jspa"
