"""Transport protocol used by SmartCoop models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .base import CommandResult

if TYPE_CHECKING:
    from .smart_coop import SmartCoop


class SmartCoopApi(Protocol):
    """Transport operations used by a SmartCoop instance."""

    async def get_smart_coops(self) -> list[SmartCoop]: ...

    async def _press_light(self, smart_coop_id: str) -> CommandResult: ...

    async def _press_feeder(self, smart_coop_id: str) -> CommandResult: ...

    async def _press_door(self, smart_coop_id: str) -> CommandResult: ...

    async def _acknowledge_errors(
        self, smart_coop_id: str, error_codes: list[int]
    ) -> CommandResult: ...
