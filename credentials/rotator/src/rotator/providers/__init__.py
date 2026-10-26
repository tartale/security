from collections.abc import Mapping

from rotator import inventory
from rotator.providers.base import Provider, ProviderError
from rotator.providers.cloudflare import Cloudflare
from rotator.providers.jira import JiraDataCenter


def for_credential(credential: inventory.Credential, environ: Mapping[str, str]) -> Provider:
    if credential.provider == "cloudflare":
        return Cloudflare.from_ref(credential.provider_ref, environ)
    if credential.provider == "jira-data-center":
        return JiraDataCenter.from_credential(credential, environ)
    raise ProviderError(f"{credential.id}: no adapter for provider {credential.provider}")


__all__ = ["Cloudflare", "JiraDataCenter", "Provider", "ProviderError", "for_credential"]
