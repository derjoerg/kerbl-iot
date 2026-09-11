"""Light component model for SmartCoop devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .base import CommandResult, copy_dataclass_fields, dataclass_to_diagnostics
from .smart_coop_component import SmartCoopComponentMixin

if TYPE_CHECKING:
    from .smart_coop import SmartCoop


@dataclass(slots=True)
class SmartCoopLight(SmartCoopComponentMixin):
    """Light component values from a SmartCoop payload."""

    id: str | None
    current_dim_value: int | None
    evening_on_time: int | None
    morning_on_time: int | None
    mode: int | None
    dark_time: str | None
    closing_mode: int | None
    _component_name = "Light"

    @property
    def is_on(self) -> bool | None:
        """Return whether the reported dim value indicates an active light."""
        if self.current_dim_value is None:
            return None
        return self.current_dim_value > 0

    async def press(self) -> CommandResult:
        """Press the SmartCoop manual light command."""
        smart_coop = self._require_smart_coop()
        return await smart_coop._require_api()._press_light(smart_coop.id)

    async def turn_on(self) -> SmartCoop:
        """Turn the light on and wait for state confirmation."""
        return await self._set_state(True)

    async def turn_off(self) -> SmartCoop:
        """Turn the light off and wait for state confirmation."""
        return await self._set_state(False)

    async def wait_for_state(self, is_on: bool, timeout: float = 30.0) -> SmartCoop:
        """Wait for the light to report the expected on/off state."""
        smart_coop = self._require_smart_coop()
        return await smart_coop._wait_for(lambda: self.is_on is is_on, timeout)

    def update_from_api(self, light: SmartCoopLight) -> None:
        """Update this component in place from a parsed API component."""
        copy_dataclass_fields(self, light)

    def to_diagnostics(self) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic snapshot of this light component."""
        diagnostics = dataclass_to_diagnostics(self)
        diagnostics["is_on"] = self.is_on
        return diagnostics

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> SmartCoopLight:
        """Create a light component from the nested ``light`` payload."""
        data = data or {}
        return cls(
            id=data.get("id"),
            current_dim_value=data.get("currentDimValue"),
            evening_on_time=data.get("eveningOnTime"),
            morning_on_time=data.get("morningOnTime"),
            mode=data.get("mode"),
            dark_time=data.get("darkTime"),
            closing_mode=data.get("closingMode"),
        )

    async def _set_state(self, is_on: bool) -> SmartCoop:
        smart_coop = self._require_smart_coop()
        async with smart_coop._command_lock:
            await smart_coop.refresh_state()
            if self.is_on is None:
                raise RuntimeError("SmartCoop does not report a light state.")
            if self.is_on is is_on:
                return smart_coop
            await self.press()
            return await self.wait_for_state(is_on)
