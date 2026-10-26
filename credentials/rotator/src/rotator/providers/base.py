from typing import Protocol


class ProviderError(Exception):
    pass


class Provider(Protocol):
    """Where a credential is minted. Errors never contain secret values."""

    capability: str
    rolls_in_place: bool

    def create(self) -> str:
        """Mint a new secret. If `rolls_in_place`, the previous secret stops working."""
        ...

    def verify(self, secret: str) -> None: ...
