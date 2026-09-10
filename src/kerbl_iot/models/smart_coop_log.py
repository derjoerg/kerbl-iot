"""Log model for SmartCoop devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


ERROR_REASON_TRANSLATIONS = {
    "errorReason.doorLocked": "Klappe verriegelt",
    "errorReason.doorClosingSoon": "Klappe schliesst bald",
    "errorReason.feederLocked": "Futterautomat gesperrt",
    "errorReason.batteryLow": "Akku schwach",
    "errorReason.waterHeaterActive": "Wasserheizung aktiv",
    "errorReason.waterEmpty": "Wasser leer",
    "errorReason.feederError": "Futterautomatenstoerung",
    "errorReason.feedEmpty": "Futter leer",
    "errorReason.batteryEmpty": "Akku leer",
    "errorReason.doorError": "Klappenstoerung",
    "errorReason.waterTemperatureLow": "Wassertemperatur zu niedrig",
    "errorReason.externalLightError": "Fremdlichtstoerung",
    "errorReason.timeError": "Uhrzeit muss eingestellt werden",
    "errorReason.flashError": "Flash-Fehler",
}


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

    @property
    def error_message(self) -> str:
        """Return the local German error text, or the API key if unknown."""
        return ERROR_REASON_TRANSLATIONS.get(self.error_key, self.error_key)

    @property
    def timestamp_display(self) -> str:
        """Return the device timestamp for display, or a clear unknown marker."""
        if self.occurred_at is None:
            return "Zeitpunkt unbekannt"
        return self.occurred_at.strftime("%Y-%m-%d %H:%M")

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