"""Water heater component model for SmartCoop devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import copy_dataclass_fields


@dataclass(slots=True)
class SmartCoopWaterHeater:
    """Water heater component values from a SmartCoop payload."""

    id: str | None
    water_temperature: float | None
    water_sensor_state: bool | None
    has_water_sensor: bool | None

    @property
    def has_temperature_reading(self) -> bool:
        """Return whether the water heater reports a water temperature."""
        return self.water_temperature is not None

    def update_from_api(self, water_heater: "SmartCoopWaterHeater") -> None:
        """Update this component in place from a parsed API component."""
        copy_dataclass_fields(self, water_heater)

    def to_diagnostics(self) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic snapshot of this water heater component."""
        return {
            "id": self.id,
            "water_temperature": self.water_temperature,
            "water_sensor_state": self.water_sensor_state,
            "has_water_sensor": self.has_water_sensor,
            "has_temperature_reading": self.has_temperature_reading,
        }

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> "SmartCoopWaterHeater":
        """Create a water heater component from the nested ``waterHeater`` payload."""
        data = data or {}
        return cls(
            id=data.get("id"),
            water_temperature=data.get("waterTemperature"),
            water_sensor_state=data.get("waterSensorState"),
            has_water_sensor=data.get("hasWaterSensor"),
        )