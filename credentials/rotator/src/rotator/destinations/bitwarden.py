import base64
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from rotator.destinations.base import DestinationError

HIDDEN_FIELD = 1


@dataclass(frozen=True)
class BitwardenBackup:
    item: dict[str, Any] = field(repr=False)


class Bitwarden:
    """A field of a Bitwarden vault item, via the `bw` CLI.

    `password` is the login password; any other name is a custom field. The secret travels to
    `bw` on stdin as base64 JSON, never in argv. The session comes from `BW_SESSION`.
    """

    def __init__(self, item: str, field: str = "password") -> None:
        self.item = item
        self.field = field

    def read_current(self) -> BitwardenBackup:
        return BitwardenBackup(self._get())

    def write(self, secret: str) -> None:
        item = self._get()
        if self.field == "password":
            if not isinstance(item.get("login"), dict):
                raise DestinationError(f"{self.item}: item has no login to hold a password")
            item["login"]["password"] = secret
        else:
            fields = item.get("fields") or []
            for f in fields:
                if f.get("name") == self.field:
                    f["value"] = secret
                    break
            else:
                fields.append(
                    {"name": self.field, "value": secret, "type": HIDDEN_FIELD, "linkedId": None}
                )
            item["fields"] = fields
        self._edit(item, secret)

    def restore(self, backup: BitwardenBackup) -> None:
        self._edit(backup.item)

    def _get(self) -> dict[str, Any]:
        out = self._bw(["get", "item", self.item])
        try:
            return json.loads(out)
        except json.JSONDecodeError as e:
            raise DestinationError(f"{self.item}: unexpected output from bw") from e

    def _edit(self, item: dict[str, Any], *secrets: str) -> None:
        encoded = base64.b64encode(json.dumps(item).encode()).decode()
        self._bw(["edit", "item", item["id"]], stdin=encoded, scrub=secrets)

    def _bw(self, args: list[str], stdin: str | None = None, scrub: tuple[str, ...] = ()) -> str:
        bw = shutil.which("bw")
        if bw is None:
            raise DestinationError("bw not found on PATH; install the Bitwarden CLI")
        if not os.environ.get("BW_SESSION"):
            raise DestinationError("BW_SESSION is not set; unlock the vault with `bw unlock`")
        result = subprocess.run(
            [bw, "--nointeraction", *args], input=stdin, capture_output=True, text=True
        )
        if result.returncode != 0:
            message = (result.stderr.strip().splitlines() or ["bw failed"])[0]
            for secret in scrub:
                message = message.replace(secret, "[redacted]")
            raise DestinationError(f"{self.item}: {message}")
        return result.stdout
