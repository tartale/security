import pytest

from rotator import flow, inventory
from rotator.destinations import DestinationError
from rotator.providers import ProviderError


class FakeProvider:
    def __init__(self, capability="auto", rolls_in_place=False, revoke_url="https://c/revoke"):
        self.capability = capability
        self.rolls_in_place = rolls_in_place
        self._revoke_url = revoke_url
        self.verified: list[str] = []
        self.fail_verify_on: int | None = None
        self.fail_create = False

    def create(self):
        if self.fail_create:
            raise ProviderError("boom")
        return "new-secret"

    def console_url(self):
        return "https://c/create"

    def revoke_url(self):
        return self._revoke_url

    def verify(self, secret):
        self.verified.append(secret)
        if self.fail_verify_on == len(self.verified):
            raise ProviderError("rejected")


class FakeDestination:
    def __init__(self, value="old", fail_writes=0, fail_restore=False):
        self.value = value
        self.fail_writes = fail_writes
        self.fail_restore = fail_restore

    def read_current(self):
        return self.value

    def write(self, secret):
        if self.fail_writes:
            self.fail_writes -= 1
            raise DestinationError("disk full")
        self.value = secret

    def restore(self, backup):
        if self.fail_restore:
            raise DestinationError("nope")
        self.value = backup


class FakePrompter:
    def __init__(self, confirms=(True,), acknowledge=True, secret="pasted-secret"):
        self.confirms = list(confirms)
        self.acknowledge_answer = acknowledge
        self.secret = secret
        self.opened: list[str] = []
        self.asked: list[str] = []

    def open_url(self, url):
        self.opened.append(url)

    def read_secret(self, prompt):
        return f"  {self.secret}\n"

    def confirm(self, message):
        self.asked.append(message)
        return self.confirms.pop(0) if len(self.confirms) > 1 else self.confirms[0]

    def acknowledge(self, message):
        self.asked.append(message)
        return self.acknowledge_answer


CREDENTIAL = inventory.Credential(
    id="c",
    provider="p",
    mode="auto",
    store=inventory.Store(type="bitwarden", item="i"),
    destinations=[],
    rotate_every_days=30,
)


def run(provider, *dests, prompter=None):
    prompter = prompter or FakePrompter()
    targets = [flow.Target(f"d{i}", d) for i, d in enumerate(dests)]
    log: list[tuple[str, str]] = []
    outcome = flow.rotate(CREDENTIAL, provider, targets, prompter, lambda s, d: log.append((s, d)))
    return outcome, prompter, log


def test_auto_flow_writes_everywhere_verifies_and_asks_to_revoke():
    provider, store, env = FakeProvider(), FakeDestination(), FakeDestination()
    outcome, prompter, _ = run(provider, store, env)
    assert (store.value, env.value) == ("new-secret", "new-secret")
    assert provider.verified == ["new-secret", "new-secret"]
    assert prompter.opened == ["https://c/revoke"]
    assert outcome.old_revoked


def test_assisted_flow_opens_console_and_uses_the_stripped_pasted_secret():
    provider, store = FakeProvider(capability="assisted"), FakeDestination()
    _, prompter, _ = run(provider, store)
    assert store.value == "pasted-secret"
    assert prompter.opened == ["https://c/create", "https://c/revoke"]


def test_declined_overwrite_does_nothing():
    provider, store = FakeProvider(), FakeDestination()
    with pytest.raises(flow.RotationError, match="cancelled"):
        run(provider, store, prompter=FakePrompter(confirms=[False]))
    assert provider.verified == []
    assert store.value == "old"


def test_empty_pasted_secret_is_rejected():
    with pytest.raises(flow.RotationError, match="no secret"):
        run(
            FakeProvider(capability="assisted"),
            FakeDestination(),
            prompter=FakePrompter(secret=""),
        )


def test_create_failure_aborts_before_writing():
    provider, store = FakeProvider(), FakeDestination()
    provider.fail_create = True
    with pytest.raises(flow.RotationError, match="could not create"):
        run(provider, store)
    assert store.value == "old"


def test_failed_verification_writes_nothing():
    provider, store = FakeProvider(), FakeDestination()
    provider.fail_verify_on = 1
    with pytest.raises(flow.RotationError, match="failed verification"):
        run(provider, store)
    assert store.value == "old"


def test_destination_failure_rolls_back_and_never_revokes():
    provider = FakeProvider()
    store, ok, bad = FakeDestination(), FakeDestination("keep"), FakeDestination(fail_writes=1)
    prompter = FakePrompter()
    with pytest.raises(flow.RotationError, match=r"d2 failed.*Old credential kept"):
        run(provider, store, ok, bad, prompter=prompter)
    assert (store.value, ok.value, bad.value) == ("old", "keep", "old")
    assert "https://c/revoke" not in prompter.opened


def test_rollback_failure_is_reported():
    store, bad = FakeDestination(fail_restore=True), FakeDestination(fail_writes=1)
    with pytest.raises(flow.RotationError, match="could not restore: d0"):
        run(FakeProvider(), store, bad)


def test_post_write_verification_failure_stops_before_revoke():
    provider = FakeProvider()
    provider.fail_verify_on = 2
    prompter = FakePrompter()
    with pytest.raises(flow.RotationError, match="post-write"):
        run(provider, FakeDestination(), prompter=prompter)
    assert prompter.opened == []


def test_unacknowledged_revoke_is_reported():
    prompter = FakePrompter(acknowledge=False)
    outcome, _, log = run(FakeProvider(), FakeDestination(), prompter=prompter)
    assert not outcome.old_revoked
    assert ("revoke old", "NOT done; the old credential still works") in log


def test_no_revoke_url_means_nothing_to_revoke():
    outcome, prompter, _ = run(FakeProvider(revoke_url=None), FakeDestination())
    assert outcome.old_revoked
    assert prompter.opened == []


def test_rolling_provider_retries_instead_of_rolling_back():
    provider = FakeProvider(rolls_in_place=True)
    store, flaky = FakeDestination(), FakeDestination(fail_writes=1)
    outcome, prompter, _ = run(provider, store, flaky)
    assert (store.value, flaky.value) == ("new-secret", "new-secret")
    assert any("Retry" in m for m in prompter.asked)
    assert outcome.old_revoked
    assert prompter.opened == []


def test_rolling_provider_reports_what_was_not_written_when_retry_declined():
    provider = FakeProvider(rolls_in_place=True)
    store, bad = FakeDestination(), FakeDestination(fail_writes=5)
    prompter = FakePrompter(confirms=[True, False])
    with pytest.raises(flow.RotationError, match=r"already invalid.*d1"):
        run(provider, store, bad, prompter=prompter)
    assert store.value == "new-secret"


def test_plan_lists_steps_without_side_effects():
    steps = flow.plan(FakeProvider(), [flow.Target("a", FakeDestination())])
    assert steps[0].startswith("create")
    assert "write to a" in steps
    assert steps[-1].startswith("open the console to revoke")
    rolling = flow.plan(FakeProvider(rolls_in_place=True), [])
    assert "invalidated the old credential" in rolling[-1]
