"""Log model for SmartCoop devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class SmartCoopLog:
    """A SmartCoop error or informational log entry."""

    time: str
    date: str
    active: bool
    error_code: int
    error_key: str
    level: str
    occurred_at: datetime | None
    received_at: datetime

    def to_diagnostics(self) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic snapshot of this log entry."""
        return {
            "time": self.time,
            "date": self.date,
            "active": self.active,
            "error_code": self.error_code,
            "error_key": self.error_key,
            "level": self.level,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "received_at": self.received_at.isoformat(),
        }

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "SmartCoopLog":
        """Create a log entry from an item in the API ``logs`` array."""
        error_reason = data["errorReason"]
        raw_date = data["date"]
        raw_time = data["time"]
        return cls(
            time=raw_time,
            date=raw_date,
            active=bool(data["active"]),
            error_code=error_reason["plain"],
            error_key=error_reason["i18nKey"],
            level=data["level"],
            occurred_at=_parse_log_timestamp(raw_date, raw_time),
            received_at=datetime.now(timezone.utc),
        )


def _parse_log_timestamp(date: str, time: str) -> datetime | None:
    """Parse a device timestamp while rejecting the known year-2000 placeholder."""
    try:
        timestamp = datetime.strptime(f"{date} {time}", "%Y.%m.%d %H:%M")
    except ValueError:
        return None
    return None if timestamp.year == 2000 else timestamp