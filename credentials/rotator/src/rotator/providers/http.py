from typing import Any

import httpx

from rotator.providers.base import ProviderError


def send(service: str, method: str, url: str, bearer: str, **kwargs: Any) -> httpx.Response:
    """Authenticated request. Errors name the service and call, never the bearer token."""
    try:
        return httpx.request(
            method, url, headers={"Authorization": f"Bearer {bearer}"}, timeout=30, **kwargs
        )
    except httpx.HTTPError as e:
        raise ProviderError(f"{service}: {type(e).__name__} calling {method} {url}") from e
