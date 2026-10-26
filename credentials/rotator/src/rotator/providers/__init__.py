from collections.abc import Mapping

from rotator import inventory
from rotator.providers.base import AssistedProvider, AutoProvider, Provider, ProviderError
from rotator.providers.cloudflare import Cloudflare
from rotator.providers.github import GitHub
from rotator.providers.jira import JiraDataCenter
from rotator.providers.runpod import RunPod


def for_credential(credential: inventory.Credential, environ: Mapping[str, str]) -> Provider:
    match credential.provider:
        case "cloudflare":
            provider: Provider = Cloudflare.from_ref(credential.provider_ref, environ)
        case "jira-data-center":
            provider = JiraDataCenter.from_credential(credential, environ)
        case "github" | "github-enterprise":
            enterprise = credential.provider == "github-enterprise"
            provider = GitHub.from_credential(credential, enterprise)
        case "runpod":
            provider = RunPod()
        case _:
            raise ProviderError(f"{credential.id}: no adapter for provider {credential.provider}")
    if credential.mode != provider.capability:
        raise ProviderError(
            f"{credential.id}: provider {credential.provider} is {provider.capability}, "
            f"inventory says mode: {credential.mode}"
        )
    return provider


__all__ = [
    "AssistedProvider",
    "AutoProvider",
    "Cloudflare",
    "GitHub",
    "JiraDataCenter",
    "Provider",
    "ProviderError",
    "RunPod",
    "for_credential",
]
