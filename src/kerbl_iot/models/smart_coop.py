"""Model for Kerbl SmartCoop devices."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .base import CommandResult, copy_dataclass_fields
from .smart_coop_brightness import SmartCoopBrightness
from .smart_coop_door import SmartCoopDoor
from .smart_coop_feeder import SmartCoopFeeder
from .smart_coop_light import SmartCoopLight
from .smart_coop_water_heater import SmartCoopWaterHeater

if TYPE_CHECKING:
    from .smart_coop_api import SmartCoopApi


@dataclass(slots=True)
class SmartCoop:
    """A SmartCoop device and its latest reported component values."""

    id: str
    user_id: str
    name: str
    online: bool
    firmware_version: str | None
    air_temperature: float | None
    door: SmartCoopDoor
    feeder: SmartCoopFeeder
    water_heater: SmartCoopWaterHeater
    light: SmartCoopLight
    brightness: SmartCoopBrightness
    current_error_reason: str | None = None
    error_reason_history: str | None = None
    _api: "SmartCoopApi | None" = field(default=None, repr=False, compare=False)
    _command_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _update_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _callbacks: set[Callable[[], None]] = field(default_factory=set, init=False, repr=False)

    async def acknowledge_errors(self, error_codes: list[int]) -> CommandResult:
        """Acknowledge active SmartCoop errors by their numeric codes."""
        return await self._require_api()._acknowledge_errors(self.id, error_codes)

    def __post_init__(self) -> None:
        self._attach_components()

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
        copy_dataclass_fields(self, smart_coop)
        self.door.update_from_api(smart_coop.door)
        self.feeder.update_from_api(smart_coop.feeder)
        self.water_heater.update_from_api(smart_coop.water_heater)
        self.light.update_from_api(smart_coop.light)
        self.brightness.update_from_api(smart_coop.brightness)
        self._update_event.set()
        for callback in self._callbacks:
            callback()

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked after a SmartCoop state update."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered state-update callback."""
        self._callbacks.discard(callback)

    def to_diagnostics(self) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic snapshot of this SmartCoop."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "online": self.online,
            "firmware_version": self.firmware_version,
            "air_temperature": self.air_temperature,
            "current_error_reason": self.current_error_reason,
            "error_reason_history": self.error_reason_history,
            "door": self.door.to_diagnostics(),
            "feeder": self.feeder.to_diagnostics(),
            "water_heater": self.water_heater.to_diagnostics(),
            "light": self.light.to_diagnostics(),
            "brightness": self.brightness.to_diagnostics(),
        }

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

    def _attach_components(self) -> None:
        self.door.attach(self)
        self.feeder.attach(self)
        self.light.attach(self)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], api: "SmartCoopApi | None" = None
    ) -> "SmartCoop":
        """Create a model from an item in the ``smartCoop`` API array."""
        return cls(
            id=data["id"],
            user_id=data["userId"],
            name=data.get("description") or data["id"],
            online=bool(data.get("isOnline")),
            firmware_version=data.get("firmwareVersion"),
            air_temperature=data.get("airTemperature"),
            door=SmartCoopDoor.from_api(data.get("door")),
            feeder=SmartCoopFeeder.from_api(data.get("feeder")),
            water_heater=SmartCoopWaterHeater.from_api(data.get("waterHeater")),
            light=SmartCoopLight.from_api(data.get("light")),
            brightness=SmartCoopBrightness.from_api(data.get("brightness")),
            current_error_reason=data.get("currentErrorReason"),
            error_reason_history=data.get("errorReasonHistory"),
            _api=api,
        )
