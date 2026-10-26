from collections.abc import Mapping
from typing import Any

import httpx

from rotator.providers.base import ProviderError

API = "https://api.cloudflare.com/client/v4"
DEFAULT_MANAGER_TOKEN_ENV = "CLOUDFLARE_ROTATOR_TOKEN"
REF_FIELDS = {"token_id", "account_id", "manager_token_env"}


class Cloudflare:
    """A Cloudflare API token, rolled in place (same token id, new secret).

    Rolling needs a manager token with "API Tokens Write" (user tokens) or "Account API Tokens
    Write" (account tokens), and invalidates the previous secret.
    """

    capability = "auto"
    rolls_in_place = True

    def __init__(self, token_id: str, manager_token: str, account_id: str | None = None) -> None:
        self.token_id = token_id
        self.account_id = account_id
        self._manager_token = manager_token
        owner = f"/accounts/{account_id}" if account_id else "/user"
        self._roll_path = f"{owner}/tokens/{token_id}/value"
        self._verify_path = f"{owner}/tokens/verify"

    @classmethod
    def from_ref(cls, ref: Mapping[str, Any], environ: Mapping[str, str]) -> "Cloudflare":
        unknown = ref.keys() - REF_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ProviderError(f"cloudflare provider_ref: unknown field {names}")
        if not ref.get("token_id"):
            raise ProviderError("cloudflare provider_ref: missing token_id")
        env_name = ref.get("manager_token_env", DEFAULT_MANAGER_TOKEN_ENV)
        manager_token = environ.get(env_name)
        if not manager_token:
            raise ProviderError(f"{env_name} is not set; it must hold a token that can roll tokens")
        return cls(ref["token_id"], manager_token, ref.get("account_id"))

    def create(self) -> str:
        result = self._call("PUT", self._roll_path, self._manager_token, json={})
        if not isinstance(result, str) or not result:
            raise ProviderError("cloudflare: roll returned no token value")
        return result

    def verify(self, secret: str) -> None:
        result = self._call("GET", self._verify_path, secret)
        if not isinstance(result, dict) or result.get("status") != "active":
            raise ProviderError("cloudflare: new token is not active")
        if result.get("id") != self.token_id:
            raise ProviderError("cloudflare: new token belongs to a different token id")

    def _call(self, method: str, path: str, bearer: str, **kwargs: Any) -> Any:
        try:
            response = httpx.request(
                method,
                API + path,
                headers={"Authorization": f"Bearer {bearer}"},
                timeout=30,
                **kwargs,
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"cloudflare: {type(e).__name__} calling {method} {path}") from e
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.is_error or not body.get("success"):
            errors = body.get("errors") or []
            detail = "; ".join(f"{e.get('code')}: {e.get('message')}" for e in errors)
            raise ProviderError(
                f"cloudflare: {method} {path} failed ({response.status_code})"
                + (f": {detail}" if detail else "")
            )
        return body.get("result")
