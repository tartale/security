from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from rotator import destinations, inventory
from rotator.destinations import Destination, DestinationError
from rotator.providers import AssistedProvider, AutoProvider, Provider, ProviderError

Report = Callable[[str, str], None]


class RotationError(Exception):
    pass


class Prompter(Protocol):
    def open_url(self, url: str) -> None: ...

    def read_secret(self, prompt: str) -> str:
        """Masked input."""
        ...

    def confirm(self, message: str) -> bool:
        """A go-ahead question the caller may auto-answer."""
        ...

    def acknowledge(self, message: str) -> bool:
        """Has the user done a manual step? Never auto-answered."""
        ...


@dataclass(frozen=True)
class Target:
    label: str
    adapter: Destination


@dataclass(frozen=True)
class Outcome:
    old_revoked: bool


def targets_for(credential: inventory.Credential) -> list[Target]:
    """The store first, then each destination."""
    store = credential.store
    targets = [Target(f"{store.type} {store.item}", destinations.for_store(store))]
    for d in credential.destinations:
        targets.append(Target(f"{d.path} {d.var}", destinations.for_destination(d)))
    return targets


def plan(provider: Provider, targets: Sequence[Target]) -> list[str]:
    if provider.capability == "auto":
        steps = ["create new credential via the provider API"]
    else:
        steps = ["open the console to create the new credential; paste it (hidden)"]
    steps.append("verify the new credential")
    steps += [f"write to {t.label}" for t in targets]
    steps.append("verify the new credential again")
    if provider.rolls_in_place:
        steps.append("(the provider invalidated the old credential when it was rolled)")
    elif provider.revoke_url():
        steps.append("open the console to revoke the old credential; confirm it is done")
    return steps


def rotate(
    credential: inventory.Credential,
    provider: Provider,
    targets: Sequence[Target],
    prompter: Prompter,
    report: Report,
) -> Outcome:
    """create -> verify -> store -> destinations -> verify -> revoke old.

    The old credential is revoked only after every target has the new one.
    """
    if not prompter.confirm(
        f"Rotate {credential.id}? This overwrites {len(targets)} stored value(s)."
    ):
        raise RotationError("cancelled")

    secret = _obtain(provider, prompter, report)
    try:
        provider.verify(secret)
    except ProviderError as e:
        raise RotationError(f"new credential failed verification: {e}") from e
    report("verify", "ok")

    backups = _read_backups(targets)
    if provider.rolls_in_place:
        _write_with_retry(targets, secret, prompter, report)
    else:
        _write_or_roll_back(targets, backups, secret, report)

    try:
        provider.verify(secret)
    except ProviderError as e:
        raise RotationError(f"post-write verification failed: {e}") from e
    report("verify again", "ok")

    return Outcome(old_revoked=_revoke_old(provider, prompter, report))


def _obtain(provider: Provider, prompter: Prompter, report: Report) -> str:
    try:
        if provider.capability == "auto":
            secret = cast(AutoProvider, provider).create()
            report("create", "ok")
            return secret
        url = cast(AssistedProvider, provider).console_url()
        report("open console", url)
        prompter.open_url(url)
        secret = prompter.read_secret("Paste the new secret (hidden): ").strip()
    except ProviderError as e:
        raise RotationError(f"could not create the new credential: {e}") from e
    if not secret:
        raise RotationError("no secret entered")
    return secret


def _read_backups(targets: Sequence[Target]) -> list[object]:
    try:
        return [t.adapter.read_current() for t in targets]
    except DestinationError as e:
        raise RotationError(f"could not back up current values: {e}") from e


def _write_or_roll_back(
    targets: Sequence[Target], backups: list[object], secret: str, report: Report
) -> None:
    written: list[int] = []
    for i, target in enumerate(targets):
        try:
            target.adapter.write(secret)
        except DestinationError as e:
            report(f"write {target.label}", "failed")
            failures = _restore(targets, backups, written, report)
            suffix = f"; could not restore: {', '.join(failures)}" if failures else ""
            raise RotationError(
                f"write to {target.label} failed: {e}. Old credential kept{suffix}"
            ) from e
        written.append(i)
        report(f"write {target.label}", "ok")


def _restore(
    targets: Sequence[Target], backups: list[object], written: list[int], report: Report
) -> list[str]:
    failed = []
    for i in reversed(written):
        try:
            targets[i].adapter.restore(backups[i])
            report(f"restore {targets[i].label}", "ok")
        except DestinationError:
            report(f"restore {targets[i].label}", "failed")
            failed.append(targets[i].label)
    return failed


def _write_with_retry(
    targets: Sequence[Target], secret: str, prompter: Prompter, report: Report
) -> None:
    """The old credential is already dead, so never roll back: retry until everything has it."""
    failed = []
    for target in targets:
        while True:
            try:
                target.adapter.write(secret)
            except DestinationError as e:
                report(f"write {target.label}", f"failed: {e}")
                if prompter.confirm(f"Retry writing to {target.label}?"):
                    continue
                failed.append(target.label)
            else:
                report(f"write {target.label}", "ok")
            break
    if failed:
        raise RotationError(
            f"the old credential is already invalid; the new one was not written to: "
            f"{', '.join(failed)}"
        )


def _revoke_old(provider: Provider, prompter: Prompter, report: Report) -> bool:
    if provider.rolls_in_place:
        report("revoke old", "done by the provider")
        return True
    url = provider.revoke_url()
    if url is None:
        return True
    report("open console", url)
    prompter.open_url(url)
    if prompter.acknowledge("Revoke the old credential there. Done?"):
        report("revoke old", "confirmed")
        return True
    report("revoke old", "NOT done; the old credential still works")
    return False
