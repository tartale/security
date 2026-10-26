import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from rotator.destinations.base import DestinationError

BARE = re.compile(r"[A-Za-z0-9_@%+=:,./-]+")


@dataclass(frozen=True)
class EnvFileBackup:
    content: str | None = field(repr=False)


class EnvFile:
    """A `.env` or `.envrc` file holding `VAR=value` (or `export VAR=value`) lines."""

    def __init__(self, path: Path, var: str) -> None:
        self.path = path.resolve()
        self.var = var
        self._assignment = re.compile(rf"^(\s*)(export\s+)?{re.escape(var)}\s*=")

    def read_current(self) -> EnvFileBackup:
        try:
            return EnvFileBackup(self.path.read_text())
        except FileNotFoundError:
            return EnvFileBackup(None)
        except OSError as e:
            raise DestinationError(f"{self.path}: {e.strerror}") from e

    def write(self, secret: str) -> None:
        backup = self.read_current()
        lines = (backup.content or "").splitlines(keepends=True)
        value = self._quote(secret)
        replaced = False
        for i, line in enumerate(lines):
            match = self._assignment.match(line)
            if match:
                ending = "\n" if line.endswith("\n") else ""
                lines[i] = f"{match.group(1)}{match.group(2) or ''}{self.var}={value}{ending}"
                replaced = True
        if not replaced:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            prefix = "export " if self.path.name.endswith(".envrc") else ""
            lines.append(f"{prefix}{self.var}={value}\n")
        self._replace("".join(lines))

    def restore(self, backup: EnvFileBackup) -> None:
        if backup.content is None:
            self.path.unlink(missing_ok=True)
        else:
            self._replace(backup.content)

    def _quote(self, secret: str) -> str:
        if BARE.fullmatch(secret):
            return secret
        if "'" in secret or "\n" in secret or "\r" in secret or not secret:
            raise DestinationError(
                f"{self.var}: secret cannot be quoted safely for {self.path.name} "
                "(empty, or contains a quote or newline)"
            )
        return f"'{secret}'"

    def _replace(self, content: str) -> None:
        mode = self.path.stat().st_mode & 0o777 if self.path.exists() else 0o600
        try:
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.")
        except OSError as e:
            raise DestinationError(f"{self.path}: {e.strerror}") from e
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.chmod(tmp, mode)
            os.replace(tmp, self.path)
        except OSError as e:
            Path(tmp).unlink(missing_ok=True)
            raise DestinationError(f"{self.path}: {e.strerror}") from e
