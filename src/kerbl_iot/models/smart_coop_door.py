"""Door component model for SmartCoop devices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .base import CommandResult
from .door_state import DoorState

if TYPE_CHECKING:
    from .smart_coop import SmartCoop


@dataclass(slots=True)
class SmartCoopDoor:
    """Door component values from a SmartCoop payload."""

    id: str | None
    has_no_door: bool | None
    state: DoorState | None
    closes_in_minutes: int | None
    type: int | None
    opening_mode: int | None
    relative_opening_brightness: int | None
    opening_time: str | None
    closing_mode: int | None
    relative_closing_brightness: int | None
    closing_delay_duration: int | None
    weekend_mode: int | None
    weekend_opening_time: str | None
    _smart_coop: "SmartCoop | None" = field(default=None, repr=False, compare=False)

    async def press(self) -> CommandResult:
        """Press the SmartCoop manual door command."""
        smart_coop = self._require_smart_coop()
        return await smart_coop._require_api()._press_door(smart_coop.id)

    async def open(self) -> "SmartCoop":
        """Open the door and wait for state confirmation."""
        return await self._set_state(DoorState.OPEN)

    async def close(self) -> "SmartCoop":
        """Close the door and wait for state confirmation."""
        return await self._set_state(DoorState.CLOSED)

    async def wait_for_state(
        self, state: DoorState, timeout: float = 30.0
    ) -> "SmartCoop":
        """Wait for the door to report the expected state."""
        smart_coop = self._require_smart_coop()
        return await smart_coop._wait_for(lambda: self.state is state, timeout)

    def attach(self, smart_coop: "SmartCoop") -> None:
        """Attach this component to its owning SmartCoop."""
        self._smart_coop = smart_coop

    def update_from_api(self, door: "SmartCoopDoor") -> None:
        """Update this component in place from a parsed API component."""
        for attribute in (
            "id", "has_no_door", "state", "closes_in_minutes", "type",
            "opening_mode", "relative_opening_brightness", "opening_time",
            "closing_mode", "relative_closing_brightness",
            "closing_delay_duration", "weekend_mode", "weekend_opening_time",
        ):
            setattr(self, attribute, getattr(door, attribute))

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> "SmartCoopDoor":
        """Create a door component from the nested ``door`` payload."""
        data = data or {}
        state = data.get("state")
        return cls(
            id=data.get("id"),
            has_no_door=data.get("hasNoDoor"),
            state=DoorState(state) if state is not None else None,
            closes_in_minutes=data.get("doorClosesInMin"),
            type=data.get("type"),
            opening_mode=data.get("openingMode"),
            relative_opening_brightness=data.get("relativeOpeningBrightness"),
            opening_time=data.get("openingTime"),
            closing_mode=data.get("closingMode"),
            relative_closing_brightness=data.get("relativeClosingBrightness"),
            closing_delay_duration=data.get("closingDelayDuration"),
            weekend_mode=data.get("weekendMode"),
            weekend_opening_time=data.get("weekendOpeningTime"),
        )

    async def _set_state(self, state: DoorState) -> "SmartCoop":
        smart_coop = self._require_smart_coop()
        async with smart_coop._command_lock:
            await smart_coop.refresh_state()
            if self.state is state:
                return smart_coop
            if self.state not in (DoorState.OPEN, DoorState.CLOSED):
                raise RuntimeError("Door is not in a stable state.")
            await self.press()
            return await self.wait_for_state(state, timeout=120.0)

    def _require_smart_coop(self) -> "SmartCoop":
        if self._smart_coop is None:
            raise RuntimeError("Door is not attached to a SmartCoop.")
        return self._smart_coop