import httpx
import pytest
import respx

from rotator import inventory, providers
from rotator.providers import Cloudflare, ProviderError

API = "https://api.cloudflare.com/client/v4"
TOKEN_ID = "ed17574386854bf78a67040be0a770b0"
ACCOUNT_ID = "a" * 32


def ok(result):
    body = {"success": True, "errors": [], "messages": [], "result": result}
    return httpx.Response(200, json=body)


def failure(status, code, message):
    errors = [{"code": code, "message": message}]
    return httpx.Response(status, json={"success": False, "errors": errors, "result": None})


@respx.mock
def test_create_rolls_user_token_with_manager_token():
    route = respx.put(f"{API}/user/tokens/{TOKEN_ID}/value").mock(
        return_value=ok("new-secret-value")
    )
    assert Cloudflare(TOKEN_ID, "manager").create() == "new-secret-value"
    assert route.calls.last.request.headers["Authorization"] == "Bearer manager"


@respx.mock
def test_create_rolls_account_token_when_account_id_given():
    route = respx.put(f"{API}/accounts/{ACCOUNT_ID}/tokens/{TOKEN_ID}/value").mock(
        return_value=ok("new")
    )
    assert Cloudflare(TOKEN_ID, "manager", ACCOUNT_ID).create() == "new"
    assert route.called


@respx.mock
def test_verify_uses_the_new_secret():
    route = respx.get(f"{API}/user/tokens/verify").mock(
        return_value=ok({"id": TOKEN_ID, "status": "active"})
    )
    Cloudflare(TOKEN_ID, "manager").verify("new-secret")
    assert route.calls.last.request.headers["Authorization"] == "Bearer new-secret"


@respx.mock
def test_verify_account_token_endpoint():
    respx.get(f"{API}/accounts/{ACCOUNT_ID}/tokens/verify").mock(
        return_value=ok({"id": TOKEN_ID, "status": "active"})
    )
    Cloudflare(TOKEN_ID, "manager", ACCOUNT_ID).verify("new")


@respx.mock
@pytest.mark.parametrize(
    "result",
    [{"id": TOKEN_ID, "status": "disabled"}, {"id": "other", "status": "active"}, None],
)
def test_verify_rejects_inactive_or_foreign_tokens(result):
    respx.get(f"{API}/user/tokens/verify").mock(return_value=ok(result))
    with pytest.raises(ProviderError):
        Cloudflare(TOKEN_ID, "manager").verify("new")


@respx.mock
def test_api_errors_report_cloudflare_codes_without_secrets():
    respx.put(f"{API}/user/tokens/{TOKEN_ID}/value").mock(
        return_value=failure(403, 9109, "Unauthorized to access requested resource")
    )
    with pytest.raises(ProviderError, match=r"403.*9109: Unauthorized") as e:
        Cloudflare(TOKEN_ID, "manager-secret").create()
    assert "manager-secret" not in str(e.value)


@respx.mock
def test_network_failure_is_a_clean_error():
    respx.put(f"{API}/user/tokens/{TOKEN_ID}/value").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(ProviderError, match="ConnectError"):
        Cloudflare(TOKEN_ID, "manager").create()


@respx.mock
def test_non_json_error_response():
    respx.put(f"{API}/user/tokens/{TOKEN_ID}/value").mock(
        return_value=httpx.Response(502, text="bad gateway")
    )
    with pytest.raises(ProviderError, match="502"):
        Cloudflare(TOKEN_ID, "manager").create()


@respx.mock
def test_empty_roll_result_is_an_error():
    respx.put(f"{API}/user/tokens/{TOKEN_ID}/value").mock(return_value=ok(None))
    with pytest.raises(ProviderError, match="no token value"):
        Cloudflare(TOKEN_ID, "manager").create()


def test_from_ref_reads_manager_token_from_default_env():
    cf = Cloudflare.from_ref({"token_id": TOKEN_ID}, {"CLOUDFLARE_ROTATOR_TOKEN": "m"})
    assert cf.token_id == TOKEN_ID
    assert cf.account_id is None


def test_from_ref_custom_env_and_account():
    cf = Cloudflare.from_ref(
        {"token_id": TOKEN_ID, "account_id": ACCOUNT_ID, "manager_token_env": "MY_CF"},
        {"MY_CF": "m"},
    )
    assert cf.account_id == ACCOUNT_ID


@pytest.mark.parametrize(
    ("ref", "environ", "message"),
    [
        ({}, {"CLOUDFLARE_ROTATOR_TOKEN": "m"}, "missing token_id"),
        ({"token_id": "x", "nope": 1}, {"CLOUDFLARE_ROTATOR_TOKEN": "m"}, "unknown field nope"),
        ({"token_id": "x"}, {}, "CLOUDFLARE_ROTATOR_TOKEN is not set"),
    ],
)
def test_from_ref_validates(ref, environ, message):
    with pytest.raises(ProviderError, match=message):
        Cloudflare.from_ref(ref, environ)


def credential(provider, ref):
    return inventory.Credential(
        id="c",
        provider=provider,
        mode="auto",
        store=inventory.Store(type="bitwarden", item="i"),
        destinations=[],
        rotate_every_days=90,
        provider_ref=ref,
    )


def test_factory_builds_cloudflare():
    cf = providers.for_credential(
        credential("cloudflare", {"token_id": TOKEN_ID}), {"CLOUDFLARE_ROTATOR_TOKEN": "m"}
    )
    assert isinstance(cf, Cloudflare)
    assert cf.rolls_in_place


def test_factory_rejects_unimplemented_provider():
    with pytest.raises(ProviderError, match="no adapter for provider modal"):
        providers.for_credential(credential("modal", {}), {})


@respx.mock
def test_success_false_with_200_is_an_error():
    respx.put(f"{API}/user/tokens/{TOKEN_ID}/value").mock(
        return_value=httpx.Response(
            200, json={"success": False, "errors": [{"code": 1, "message": "nope"}], "result": "x"}
        )
    )
    with pytest.raises(ProviderError, match="1: nope"):
        Cloudflare(TOKEN_ID, "manager").create()
