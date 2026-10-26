from dataclasses import dataclass
from datetime import UTC, date, timedelta

from rotator import inventory
from rotator.audit import AuditLog


@dataclass(frozen=True)
class Due:
    credential_id: str
    status: str  # overdue | due soon | ok | never rotated
    due_on: date | None
    days_left: int | None


def report(
    credentials: list[inventory.Credential], audit: AuditLog, today: date, within_days: int
) -> list[Due]:
    rows = []
    for c in credentials:
        logged = audit.last_rotated(c.id)
        candidates = [c.last_rotated] if c.last_rotated else []
        if logged:
            candidates.append(logged.astimezone(UTC).date())
        if not candidates:
            rows.append(Due(c.id, "never rotated", None, None))
            continue
        due_on = max(candidates) + timedelta(days=c.rotate_every_days)
        days_left = (due_on - today).days
        status = "overdue" if days_left < 0 else "due soon" if days_left <= within_days else "ok"
        rows.append(Due(c.id, status, due_on, days_left))
    return rows

