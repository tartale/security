from rotator import inventory
from rotator.destinations.base import Destination, DestinationError
from rotator.destinations.bitwarden import Bitwarden
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
    "for_destination",
    "for_store",
]
