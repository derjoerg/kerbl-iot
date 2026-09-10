"""Coordinator for Kerbl IoT devices and updates."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .api import KerblIOTApi
from .models import SmartCoop, SmartCoopLog

_LOGGER = logging.getLogger(__name__)


class KerblIOT:
    """Load Kerbl IoT devices and keep their state current."""

    def __init__(self, api: KerblIOTApi, log_refresh_delay: float = 1.0) -> None:
        """Initialize the coordinator with an authenticated API client."""
        if log_refresh_delay < 0:
            raise ValueError("log_refresh_delay must not be negative.")
        self.api = api
        self._log_refresh_delay = log_refresh_delay
        self._smart_coops: dict[str, SmartCoop] = {}
        self._smart_coop_callbacks: list[Callable[[SmartCoop], Awaitable[None]]] = []
        self._smart_coop_log_callbacks: list[
            Callable[[SmartCoop, list[SmartCoopLog]], Awaitable[None]]
        ] = []
        self._smart_coop_logs: dict[str, list[SmartCoopLog]] = {}
        self._log_refresh_tasks: dict[str, asyncio.Task[None]] = {}
        self.api.register_smart_coop_update_callback(self._handle_smart_coop_update)

    async def load(self) -> None:
        """Load all supported devices from the API."""
        smart_coops = await self.api.get_smart_coops()
        loaded_ids = {smart_coop.id for smart_coop in smart_coops}
        for smart_coop in smart_coops:
            existing = self._smart_coops.get(smart_coop.id)
            if existing is None:
                self._smart_coops[smart_coop.id] = smart_coop
            else:
                await existing.update_from_api(smart_coop)
        self._smart_coops = {
            smart_coop_id: smart_coop
            for smart_coop_id, smart_coop in self._smart_coops.items()
            if smart_coop_id in loaded_ids
        }
        await asyncio.gather(
            *(self.refresh_smart_coop_logs(coop_id) for coop_id in loaded_ids)
        )

    async def __aenter__(self) -> "KerblIOT":
        """Authenticate, load devices, and return the coordinator."""
        await self.api.login()
        await self.load()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Cancel coordinator work and close its API transport."""
        await self.async_close()

    async def connect_websocket(self, debug: bool = False) -> None:
        """Connect the API WebSocket after devices were loaded."""
        if not self._smart_coops:
            await self.load()
        await self.api.connect_websocket(self.smart_coops, debug=debug)

    @property
    def smart_coops(self) -> list[SmartCoop]:
        """Return the loaded SmartCoop devices."""
        return list(self._smart_coops.values())

    def get_smart_coop(self, smart_coop_id: str) -> SmartCoop | None:
        """Return a loaded SmartCoop by its ID."""
        return self._smart_coops.get(smart_coop_id)

    def get_smart_coop_logs(self, smart_coop_id: str) -> list[SmartCoopLog]:
        """Return the latest authoritative log entries for a SmartCoop."""
        return self._smart_coop_logs.get(smart_coop_id, [])

    def to_diagnostics(self) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic snapshot of loaded state."""
        return {
            "smart_coops": [
                smart_coop.to_diagnostics()
                for smart_coop in self.smart_coops
            ],
            "smart_coop_logs": {
                smart_coop_id: [log.to_diagnostics() for log in logs]
                for smart_coop_id, logs in self._smart_coop_logs.items()
            },
            "websocket_connected": self.api.websocket_connected,
        }

    def register_smart_coop_update_callback(
        self, callback: Callable[[SmartCoop], Awaitable[None]]
    ) -> None:
        """Register a callback called after a SmartCoop state update."""
        self._smart_coop_callbacks.append(callback)

    def register_smart_coop_log_callback(
        self, callback: Callable[[SmartCoop, list[SmartCoopLog]], Awaitable[None]]
    ) -> None:
        """Register a callback called after SmartCoop logs are refreshed."""
        self._smart_coop_log_callbacks.append(callback)

    async def refresh_smart_coop_logs(self, smart_coop_id: str) -> list[SmartCoopLog]:
        """Refresh and cache the authoritative logs for a loaded SmartCoop."""
        smart_coop = self.get_smart_coop(smart_coop_id)
        if smart_coop is None:
            return []
        logs = await self.api.get_smart_coop_logs(smart_coop_id)
        self._smart_coop_logs[smart_coop_id] = logs
        for callback in self._smart_coop_log_callbacks:
            await callback(smart_coop, logs)
        return logs

    async def async_close(self) -> None:
        """Cancel pending work and close the underlying API transport."""
        tasks = list(self._log_refresh_tasks.values())
        self._log_refresh_tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.api.close()

    async def _handle_smart_coop_update(self, smart_coop: SmartCoop) -> None:
        """Store a WebSocket SmartCoop update and refresh logs when needed."""
        existing = self._smart_coops.get(smart_coop.id)
        if existing is None:
            self._smart_coops[smart_coop.id] = smart_coop
            current = smart_coop
            previous_signature = None
        else:
            previous_signature = self._error_signature(existing)
            await existing.update_from_api(smart_coop)
            current = existing
        for callback in self._smart_coop_callbacks:
            await callback(current)
        if previous_signature != self._error_signature(current):
            self._schedule_log_refresh(current.id)

    def _schedule_log_refresh(self, smart_coop_id: str) -> None:
        """Schedule one debounced authoritative log refresh per SmartCoop."""
        existing_task = self._log_refresh_tasks.get(smart_coop_id)
        if existing_task is not None:
            existing_task.cancel()
        task = asyncio.create_task(self._refresh_logs_after_delay(smart_coop_id))
        self._log_refresh_tasks[smart_coop_id] = task
        task.add_done_callback(
            lambda completed_task: self._discard_log_refresh_task(
                smart_coop_id, completed_task
            )
        )

    async def _refresh_logs_after_delay(self, smart_coop_id: str) -> None:
        """Wait briefly for backend consistency before refreshing SmartCoop logs."""
        try:
            await asyncio.sleep(self._log_refresh_delay)
            await self.refresh_smart_coop_logs(smart_coop_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Unable to refresh SmartCoop logs for %s", smart_coop_id)

    def _discard_log_refresh_task(
        self, smart_coop_id: str, completed_task: asyncio.Task[None]
    ) -> None:
        """Remove only the completed task currently registered for a SmartCoop."""
        if self._log_refresh_tasks.get(smart_coop_id) is completed_task:
            self._log_refresh_tasks.pop(smart_coop_id, None)

    @staticmethod
    def _error_signature(smart_coop: SmartCoop) -> tuple[str | None, str | None]:
        """Return the socket fields that indicate a possible log change."""
        return smart_coop.current_error_reason, smart_coop.error_reason_history