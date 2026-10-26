import json
import os
from datetime import UTC, datetime
from pathlib import Path


class AuditLog:
    """Append-only JSON lines: when, which credential, which step, what happened.

    Only engine-generated messages are recorded, never secret values.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, credential_id: str, provider: str, step: str, detail: str = "") -> None:
        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "credential": credential_id,
            "provider": provider,
            "step": step,
            "detail": detail,
        }
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def last_rotated(self, credential_id: str) -> datetime | None:
        """Time of the latest `rotated` entry for the credential."""
        if not self.path.exists():
            return None
        latest = None
        for line in self.path.read_text().splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("credential") == credential_id and entry.get("step") == "rotated":
                latest = datetime.fromisoformat(entry["ts"])
        return latest
