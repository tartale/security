from collections.abc import Mapping

from rotator import inventory
from rotator.providers.base import Provider, ProviderError
from rotator.providers.cloudflare import Cloudflare


def for_credential(credential: inventory.Credential, environ: Mapping[str, str]) -> Provider:
    if credential.provider == "cloudflare":
        return Cloudflare.from_ref(credential.provider_ref, environ)
    raise ProviderError(f"{credential.id}: no adapter for provider {credential.provider}")


__all__ = ["Cloudflare", "Provider", "ProviderError", "for_credential"]
