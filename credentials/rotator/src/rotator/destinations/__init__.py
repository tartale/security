from rotator import inventory
from rotator.destinations.base import Destination, DestinationError
from rotator.destinations.bitwarden import Bitwarden, ensure_session
from rotator.destinations.envfile import EnvFile


def for_destination(destination: inventory.Destination) -> Destination:
    return EnvFile(destination.path, destination.var)


def for_store(store: inventory.Store) -> Destination:
    return Bitwarden(store.item, store.field)


__all__ = [
    "Bitwarden",
    "Destination",
    "DestinationError",
    "EnvFile",
    "ensure_session",
    "for_destination",
    "for_store",
]
