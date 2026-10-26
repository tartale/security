from rotator.providers.base import ProviderError
from rotator.providers.http import send

API = "https://rest.runpod.io/v1"
CONSOLE_URL = "https://console.runpod.io/user/credentials"


class RunPod:
    """A RunPod API key. The console creates and deletes keys; the secret is shown once."""

    capability = "assisted"
    rolls_in_place = False

    def console_url(self) -> str:
        return CONSOLE_URL

    def revoke_url(self) -> str:
        return CONSOLE_URL

    def verify(self, secret: str) -> None:
        response = send("runpod", "GET", f"{API}/pods", secret)
        if response.is_error:
            raise ProviderError(f"runpod: GET /pods failed ({response.status_code})")
