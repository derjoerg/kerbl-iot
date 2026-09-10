"""Brightness component model for SmartCoop devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        for attribute in (
            "id", "external_sensor_connected", "current_brightness",
            "night_duration_start_time", "night_duration_end_time",
        ):
            setattr(self, attribute, getattr(brightness, attribute))

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