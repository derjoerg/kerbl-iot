"""Brightness component model for SmartCoop devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import copy_dataclass_fields


@dataclass(slots=True)
class SmartCoopBrightness:
    """Brightness component values from a SmartCoop payload."""

    id: str | None
    external_sensor_connected: bool | None
    current_brightness: int | None
    night_duration_start_time: int | None
    night_duration_end_time: int | None

    @property
    def is_available(self) -> bool:
        """Return whether brightness data is currently available."""
        return self.current_brightness is not None

    def update_from_api(self, brightness: "SmartCoopBrightness") -> None:
        """Update this component in place from a parsed API component."""
        copy_dataclass_fields(self, brightness)

    def to_diagnostics(self) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic snapshot of this brightness component."""
        return {
            "id": self.id,
            "external_sensor_connected": self.external_sensor_connected,
            "current_brightness": self.current_brightness,
            "is_available": self.is_available,
            "night_duration_start_time": self.night_duration_start_time,
            "night_duration_end_time": self.night_duration_end_time,
        }

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> "SmartCoopBrightness":
        """Create a brightness component from the nested ``brightness`` payload."""
        data = data or {}
        return cls(
            id=data.get("id"),
            external_sensor_connected=data.get("externalSensorConnected"),
            current_brightness=data.get("currentBrightness"),
            night_duration_start_time=data.get("nightDurationStartTime"),
            night_duration_end_time=data.get("nightDurationEndTime"),
        )