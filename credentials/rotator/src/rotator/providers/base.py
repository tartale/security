from typing import Protocol


class ProviderError(Exception):
    pass


class Provider(Protocol):
    """Where a credential is minted. Errors never contain secret values.

    `capability` is `auto` (the tool calls `create`) or `assisted` (the user creates the secret
    at `console_url`). Providers that roll in place invalidate the old secret at creation.
    """

    capability: str
    rolls_in_place: bool

    def verify(self, secret: str) -> None: ...

    def revoke_url(self) -> str | None:
        """Console page where the old credential is revoked; None if nothing to revoke."""
        ...


class AutoProvider(Provider, Protocol):
    def create(self) -> str: ...


class AssistedProvider(Provider, Protocol):
    def console_url(self) -> str: ...
