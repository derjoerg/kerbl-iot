"""Models for Kerbl SmartCoop devices."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Protocol

from .base import CommandResult

if TYPE_CHECKING:
    from ..api import KerblIOTApi


class SmartCoopApi(Protocol):
    """Transport operations used by a SmartCoop instance."""

    async def get_smart_coops(self) -> list["SmartCoop"]: ...

    async def _toggle_light(self, smart_coop_id: str) -> CommandResult: ...

    async def _toggle_feeder(self, smart_coop_id: str) -> CommandResult: ...

    async def _toggle_door(self, smart_coop_id: str) -> CommandResult: ...

    async def _acknowledge_errors(
        self, smart_coop_id: str, error_codes: list[int]
    ) -> CommandResult: ...


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


class DoorState(IntEnum):
    """Door states reported by a SmartCoop."""

    UNKNOWN = 63
    SIMULATE = 83
    OPEN = 79
    CLOSING = 99
    CLOSED = 67
    OPENING = 111
    TOGGLE_MANUAL = 116
    UNLOCK = 85
    LOCK_UNTIL_TOMORROW = 84
    LOCK_PERMANENTLY = 80


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


@dataclass(slots=True)
class SmartCoop:
    """A SmartCoop device and its latest reported values."""

    id: str
    user_id: str
    name: str
    online: bool
    air_temperature: float | None
    door_state: DoorState | None
    water_temperature: float | None
    light_dim_value: int | None
    feeding_in_progress: bool | None
    feeding_active: bool | None
    feeding_locked: bool | None
    current_brightness: int | None
    current_voltage: float | None
    current_error_reason: str | None = None
    error_reason_history: str | None = None
    _api: SmartCoopApi | None = field(default=None, repr=False, compare=False)
    _command_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _update_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _callbacks: set[Callable[[], None]] = field(default_factory=set, init=False, repr=False)

    @property
    def light_is_on(self) -> bool | None:
        """Return whether the reported light dim value indicates an active light."""
        if self.light_dim_value is None:
            return None
        return self.light_dim_value > 0

    async def toggle_light(self) -> CommandResult:
        """Toggle the SmartCoop light."""
        return await self._require_api()._toggle_light(self.id)

    async def turn_light_on(self) -> "SmartCoop":
        """Turn the SmartCoop light on and wait for state confirmation."""
        return await self._set_light_state(True)

    async def turn_light_off(self) -> "SmartCoop":
        """Turn the SmartCoop light off and wait for state confirmation."""
        return await self._set_light_state(False)

    async def toggle_feeder(self) -> CommandResult:
        """Toggle the SmartCoop feeder."""
        return await self._require_api()._toggle_feeder(self.id)

    async def acknowledge_errors(self, error_codes: list[int]) -> CommandResult:
        """Acknowledge active SmartCoop errors by their numeric codes."""
        return await self._require_api()._acknowledge_errors(self.id, error_codes)

    async def toggle_door(self) -> CommandResult:
        """Toggle the SmartCoop door."""
        return await self._require_api()._toggle_door(self.id)

    async def open_door(self) -> "SmartCoop":
        """Open the SmartCoop door and wait for state confirmation."""
        return await self._set_door_state(DoorState.OPEN)

    async def close_door(self) -> "SmartCoop":
        """Close the SmartCoop door and wait for state confirmation."""
        return await self._set_door_state(DoorState.CLOSED)

    async def wait_for_light_state(self, is_on: bool, timeout: float = 30.0) -> "SmartCoop":
        """Wait for the SmartCoop to report the expected light state."""
        return await self._wait_for(lambda: self.light_is_on is is_on, timeout)

    async def wait_for_feeding_state(
        self, in_progress: bool, timeout: float = 30.0
    ) -> "SmartCoop":
        """Wait for the SmartCoop to report the expected feeder state."""
        return await self._wait_for(
            lambda: self.feeding_in_progress is in_progress, timeout
        )

    async def wait_for_door_state(
        self, state: DoorState, timeout: float = 30.0
    ) -> "SmartCoop":
        """Wait for the SmartCoop to report the expected door state."""
        return await self._wait_for(lambda: self.door_state is state, timeout)

    async def refresh_state(self) -> None:
        """Refresh this stable SmartCoop instance from the API."""
        smart_coop = next(
            (coop for coop in await self._require_api().get_smart_coops() if coop.id == self.id),
            None,
        )
        if smart_coop is None:
            raise RuntimeError(f"No SmartCoop found with ID: {self.id}")
        await self.update_from_api(smart_coop)

    async def update_from_api(self, smart_coop: "SmartCoop") -> None:
        """Update this instance in place from an API or Socket.IO state update."""
        for attribute in (
            "user_id", "name", "online", "air_temperature", "door_state",
            "water_temperature", "light_dim_value", "feeding_in_progress",
            "feeding_active", "feeding_locked", "current_brightness",
            "current_voltage", "current_error_reason", "error_reason_history",
        ):
            setattr(self, attribute, getattr(smart_coop, attribute))
        self._update_event.set()
        for callback in self._callbacks:
            callback()

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked after a SmartCoop state update."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered state-update callback."""
        self._callbacks.discard(callback)

    async def _set_light_state(self, is_on: bool) -> "SmartCoop":
        async with self._command_lock:
            await self.refresh_state()
            if self.light_is_on is None:
                raise RuntimeError("SmartCoop does not report a light state.")
            if self.light_is_on is is_on:
                return self
            await self.toggle_light()
            return await self.wait_for_light_state(is_on)

    async def _set_door_state(self, state: DoorState) -> "SmartCoop":
        async with self._command_lock:
            await self.refresh_state()
            if self.door_state is state:
                return self
            if self.door_state not in (DoorState.OPEN, DoorState.CLOSED):
                raise RuntimeError("Door is not in a stable state.")
            await self.toggle_door()
            return await self.wait_for_door_state(state, timeout=120.0)

    async def _wait_for(
        self, condition: Callable[[], bool], timeout: float
    ) -> "SmartCoop":
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            self._update_event.clear()
            if condition():
                return self
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError("SmartCoop did not report the expected state.")
            await asyncio.wait_for(self._update_event.wait(), timeout=remaining)

    def _require_api(self) -> SmartCoopApi:
        if self._api is None:
            raise RuntimeError("SmartCoop is not attached to a KerblIOTApi client.")
        return self._api

    @classmethod
    def from_api(
        cls, data: dict[str, Any], api: "KerblIOTApi | None" = None
    ) -> "SmartCoop":
        """Create a model from an item in the ``smartCoop`` API array."""
        door = data.get("door") or {}
        water_heater = data.get("waterHeater") or {}
        brightness = data.get("brightness") or {}
        feeder = data.get("feeder") or {}
        light = data.get("light") or {}
        power = data.get("power") or {}

        door_state = door.get("state")

        return cls(
            id=data["id"],
            user_id=data["userId"],
            name=data.get("description") or data["id"],
            online=bool(data.get("isOnline")),
            air_temperature=data.get("airTemperature"),
            door_state=DoorState(door_state) if door_state is not None else None,
            water_temperature=water_heater.get("waterTemperature"),
            light_dim_value=light.get("currentDimValue"),
            feeding_in_progress=feeder.get("feedingInProgress"),
            feeding_active=feeder.get("feedingActive"),
            feeding_locked=feeder.get("feedingLocked"),
            current_brightness=brightness.get("currentBrightness"),
            current_voltage=power.get("currentVoltage"),
            current_error_reason=data.get("currentErrorReason"),
            error_reason_history=data.get("errorReasonHistory"),
            _api=api,
        )


def _parse_log_timestamp(date: str, time: str) -> datetime | None:
    """Parse a device timestamp while rejecting the known year-2000 placeholder."""
    try:
        timestamp = datetime.strptime(f"{date} {time}", "%Y.%m.%d %H:%M")
    except ValueError:
        return None
    return None if timestamp.year == 2000 else timestamp