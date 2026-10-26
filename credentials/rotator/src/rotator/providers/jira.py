from collections.abc import Mapping
from typing import Any

import httpx

from rotator import inventory
from rotator.providers.base import ProviderError

DEFAULT_CURRENT_TOKEN_ENV = "JIRA_ROTATOR_TOKEN"
EXPIRY_SLACK_DAYS = 14
REF_FIELDS = {"base_url", "token_name", "expiration_days", "current_token_env"}


class JiraDataCenter:
    """A Jira Data Center personal access token (PAT), replaced by creating a new one.

    The create call authenticates with the existing PAT as a bearer token. The old PAT keeps
    working until revoked, which is a console step.
    """

    capability = "auto"
    rolls_in_place = False

    def __init__(
        self, base_url: str, token_name: str, expiration_days: int, current_token: str
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_name = token_name
        self.expiration_days = expiration_days
        self._current_token = current_token

    @classmethod
    def from_credential(
        cls, credential: inventory.Credential, environ: Mapping[str, str]
    ) -> "JiraDataCenter":
        ref = credential.provider_ref
        unknown = ref.keys() - REF_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ProviderError(f"{credential.id}: jira provider_ref: unknown field {names}")
        if not ref.get("base_url"):
            raise ProviderError(f"{credential.id}: jira provider_ref: missing base_url")
        env_name = ref.get("current_token_env", DEFAULT_CURRENT_TOKEN_ENV)
        current_token = environ.get(env_name)
        if not current_token:
            raise ProviderError(
                f"{env_name} is not set; it must hold the current PAT (the first PAT is "
                "created by hand in the Jira UI)"
            )
        expiration_days = ref.get(
            "expiration_days",
            credential.rotate_every_days + credential.grace_days + EXPIRY_SLACK_DAYS,
        )
        if isinstance(expiration_days, bool) or not isinstance(expiration_days, int):
            raise ProviderError(
                f"{credential.id}: jira provider_ref: expiration_days must be an integer"
            )
        return cls(
            ref["base_url"], ref.get("token_name", credential.id), expiration_days, current_token
        )

    def create(self) -> str:
        body = self._call(
            "POST",
            "/rest/pat/latest/tokens",
            self._current_token,
            json={"name": self.token_name, "expirationDuration": self.expiration_days},
        )
        raw = body.get("rawToken") if isinstance(body, dict) else None
        if not isinstance(raw, str) or not raw:
            raise ProviderError("jira: create response has no rawToken (field name unverified)")
        return raw

    def verify(self, secret: str) -> None:
        self._call("GET", "/rest/api/2/myself", secret)

    def _call(self, method: str, path: str, bearer: str, **kwargs: Any) -> Any:
        try:
            response = httpx.request(
                method,
                self.base_url + path,
                headers={"Authorization": f"Bearer {bearer}"},
                timeout=30,
                **kwargs,
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"jira: {type(e).__name__} calling {method} {path}") from e
        if response.is_error:
            raise ProviderError(f"jira: {method} {path} failed ({response.status_code})")
        try:
            return response.json()
        except ValueError:
            return None
