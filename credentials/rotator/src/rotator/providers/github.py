from urllib.parse import urlencode

from rotator import inventory
from rotator.providers.base import ProviderError
from rotator.providers.http import send

DEFAULT_HOST = "github.com"
KINDS = {"fine-grained", "classic"}
REF_FIELDS = {"host", "token_name"}
EXPIRY_SLACK_DAYS = 14
MAX_EXPIRY_DAYS = 366
MAX_NAME_LENGTH = 40


class GitHub:
    """A GitHub personal access token on github.com or GitHub Enterprise Server.

    GitHub has no API to create or delete PATs, so the user creates the new one at
    `console_url` and deletes the old one at `revoke_url`.
    """

    capability = "assisted"
    rolls_in_place = False

    def __init__(self, host: str, kind: str, token_name: str, expiry_days: int) -> None:
        self.host = host
        self.kind = kind
        self.token_name = token_name[:MAX_NAME_LENGTH]
        self.expiry_days = min(expiry_days, MAX_EXPIRY_DAYS)
        self._api = (
            "https://api.github.com" if host == DEFAULT_HOST else f"https://{host}/api/v3"
        )

    @classmethod
    def from_credential(cls, credential: inventory.Credential, enterprise: bool) -> "GitHub":
        ref = credential.provider_ref
        unknown = ref.keys() - REF_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ProviderError(f"{credential.id}: github provider_ref: unknown field {names}")
        if credential.kind not in KINDS:
            raise ProviderError(
                f"{credential.id}: github needs kind: {' or '.join(sorted(KINDS))}"
            )
        host = ref.get("host", None if enterprise else DEFAULT_HOST)
        if not host:
            raise ProviderError(f"{credential.id}: github-enterprise needs provider_ref.host")
        if enterprise and host == DEFAULT_HOST:
            raise ProviderError(f"{credential.id}: use provider github for {DEFAULT_HOST}")
        expiry_days = credential.rotate_every_days + credential.grace_days + EXPIRY_SLACK_DAYS
        return cls(host, credential.kind, ref.get("token_name", credential.id), expiry_days)

    def console_url(self) -> str:
        if self.kind == "classic":
            return f"https://{self.host}/settings/tokens/new"
        query = urlencode({"name": self.token_name, "expires_in": self.expiry_days})
        return f"https://{self.host}/settings/personal-access-tokens/new?{query}"

    def revoke_url(self) -> str:
        if self.kind == "classic":
            return f"https://{self.host}/settings/tokens"
        return f"https://{self.host}/settings/personal-access-tokens"

    def verify(self, secret: str) -> None:
        response = send("github", "GET", f"{self._api}/user", secret)
        if response.is_error:
            raise ProviderError(f"github: GET /user failed ({response.status_code})")
