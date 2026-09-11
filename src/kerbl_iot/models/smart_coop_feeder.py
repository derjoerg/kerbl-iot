"""Feeder component model for SmartCoop devices."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .base import CommandResult
from .smart_coop_component import SmartCoopComponentMixin

if TYPE_CHECKING:
    from .smart_coop import SmartCoop


@dataclass(slots=True)
class SmartCoopFeeder(SmartCoopComponentMixin):
    """Feeder component values from a SmartCoop payload."""

    id: str | None
    start_time: str | None
    end_time: str | None
    feeding_interval: int | None
    interval_start_times: list[str] | None
    interval_end_times: list[str] | None
    feeding_locked: bool | None
    feeding_active: bool | None
    has_feed_sensor: bool | None
    is_feed_full: bool | None
    feeding_in_progress: bool | None
    animal_count: int | None
    amount_per_animal: int | None
    amount_per_feeding_intervals: list[int] | None
    _component_name = "Feeder"

    async def press(self) -> CommandResult:
        """Press the SmartCoop manual feeder command."""
        smart_coop = self._require_smart_coop()
        return await smart_coop._require_api()._press_feeder(smart_coop.id)

    async def wait_for_state(
        self, in_progress: bool, timeout: float = 30.0
    ) -> "SmartCoop":
        """Wait for the feeder to report the expected running state."""
        smart_coop = self._require_smart_coop()
        return await smart_coop._wait_for(
            lambda: self.feeding_in_progress is in_progress, timeout
        )

    def update_from_api(self, feeder: "SmartCoopFeeder") -> None:
        """Update this component in place from a parsed API component."""
        for attribute in (
            "id", "start_time", "end_time", "feeding_interval",
            "interval_start_times", "interval_end_times", "feeding_locked",
            "feeding_active", "has_feed_sensor", "is_feed_full",
            "feeding_in_progress", "animal_count", "amount_per_animal",
            "amount_per_feeding_intervals",
        ):
            setattr(self, attribute, getattr(feeder, attribute))

    def to_diagnostics(self) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic snapshot of this feeder component."""
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "feeding_interval": self.feeding_interval,
            "interval_start_times": self.interval_start_times,
            "interval_end_times": self.interval_end_times,
            "feeding_locked": self.feeding_locked,
            "feeding_active": self.feeding_active,
            "has_feed_sensor": self.has_feed_sensor,
            "is_feed_full": self.is_feed_full,
            "feeding_in_progress": self.feeding_in_progress,
            "animal_count": self.animal_count,
            "amount_per_animal": self.amount_per_animal,
            "amount_per_feeding_intervals": self.amount_per_feeding_intervals,
        }

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> "SmartCoopFeeder":
        """Create a feeder component from the nested ``feeder`` payload."""
        data = data or {}
        return cls(
            id=data.get("id"),
            start_time=data.get("startTime"),
            end_time=data.get("endTime"),
            feeding_interval=data.get("feedingInterval"),
            interval_start_times=_json_list(data.get("intervalStartTimes"), str),
            interval_end_times=_json_list(data.get("intervalEndTimes"), str),
            feeding_locked=data.get("feedingLocked"),
            feeding_active=data.get("feedingActive"),
            has_feed_sensor=data.get("hasFeedSensor"),
            is_feed_full=data.get("isFeedFull"),
            feeding_in_progress=data.get("feedingInProgress"),
            animal_count=data.get("animalCount"),
            amount_per_animal=data.get("amountPerAnimal"),
            amount_per_feeding_intervals=_json_list(
                data.get("amountPerFeedingIntervals"), int
            ),
        )

def _json_list(value: object, item_type: type) -> list[Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        try:
            items = json.loads(value)
        except ValueError:
            return None
    else:
        return None
    if not isinstance(items, list) or not all(isinstance(item, item_type) for item in items):
        return None
    return items