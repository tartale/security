from rotator import destinations, inventory
from rotator.destinations import EnvFile


def test_factories_build_adapters_from_inventory(tmp_path):
    d = inventory.Destination(type="envfile", path=tmp_path / ".env", var="T")
    s = inventory.Store(type="bitwarden", item="i", field="api")
    assert isinstance(destinations.for_destination(d), EnvFile)
    assert destinations.for_store(s).field == "api"
