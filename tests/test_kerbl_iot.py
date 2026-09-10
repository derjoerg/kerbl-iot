"""Tests for the Kerbl IoT device coordinator."""

import asyncio
import unittest
from unittest.mock import AsyncMock

from kerbl_iot import KerblIOT, KerblIOTApi
from kerbl_iot.models.smart_coop import SmartCoop
from kerbl_iot.models.smart_coop_log import SmartCoopLog


class KerblIOTTest(unittest.IsolatedAsyncioTestCase):
    """Verify loaded device coordination and update dispatch."""

    async def test_load_and_dispatch_smart_coop_update(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        first = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )
        updated = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "description": "Updated coop",
                "isOnline": True,
            },
            api,
        )
        api.get_smart_coops.return_value = [first]
        callback = AsyncMock()

        kerbl = KerblIOT(api)
        kerbl.register_smart_coop_update_callback(callback)
        await kerbl.load()
        await kerbl._handle_smart_coop_update(updated)

        self.assertIs(kerbl.get_smart_coop("coop-1"), first)
        self.assertEqual(first.name, "Updated coop")
        self.assertIsNone(kerbl.get_smart_coop("unknown"))
        callback.assert_awaited_once_with(first)

    async def test_connect_loads_before_connecting_socket(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        api.get_smart_coops.return_value = []
        kerbl = KerblIOT(api)

        await kerbl.connect_websocket(debug=True)

        api.get_smart_coops.assert_awaited_once()
        api.connect_websocket.assert_awaited_once_with([], debug=True)

    async def test_load_refreshes_and_caches_smart_coop_logs(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )
        api.get_smart_coops.return_value = [coop]
        api.get_smart_coop_logs.return_value = ["log-entry"]
        callback = AsyncMock()
        kerbl = KerblIOT(api)
        kerbl.register_smart_coop_log_callback(callback)

        await kerbl.load()

        self.assertEqual(kerbl.get_smart_coop_logs("coop-1"), ["log-entry"])
        api.get_smart_coop_logs.assert_awaited_once_with("coop-1")
        callback.assert_awaited_once_with(coop, ["log-entry"])

    async def test_diagnostics_dump_includes_loaded_devices_and_logs(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        type(api).websocket_connected = unittest.mock.PropertyMock(return_value=True)
        coop = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "description": "Coop",
                "firmwareVersion": "V01.34",
                "isOnline": True,
                "door": {"state": 79},
            },
            api,
        )
        log = SmartCoopLog.from_api(
            {
                "time": "07:23",
                "date": "2026.09.09",
                "active": True,
                "errorReason": {
                    "plain": 128,
                    "i18nKey": "errorReason.feedEmpty",
                },
                "level": "error",
            }
        )
        api.get_smart_coops.return_value = [coop]
        api.get_smart_coop_logs.return_value = [log]
        kerbl = KerblIOT(api)

        await kerbl.load()
        diagnostics = kerbl.to_diagnostics()

        self.assertTrue(diagnostics["websocket_connected"])
        self.assertEqual(diagnostics["smart_coops"][0]["id"], "coop-1")
        self.assertEqual(diagnostics["smart_coops"][0]["door"]["state"], "OPEN")
        self.assertEqual(
            diagnostics["smart_coop_logs"]["coop-1"][0]["error_message"],
            "Futter leer",
        )

    async def test_socket_error_change_debounces_log_refresh(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        initial = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "isOnline": True,
                "currentErrorReason": "[0]",
                "errorReasonHistory": "[]",
            },
            api,
        )
        changed = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "isOnline": True,
                "currentErrorReason": "[256]",
                "errorReasonHistory": "[256]",
            },
            api,
        )
        api.get_smart_coops.return_value = [initial]
        api.get_smart_coop_logs.return_value = []
        kerbl = KerblIOT(api, log_refresh_delay=0)
        await kerbl.load()
        api.get_smart_coop_logs.reset_mock()

        await kerbl._handle_smart_coop_update(initial)
        await asyncio.sleep(0)
        api.get_smart_coop_logs.assert_not_awaited()

        await kerbl._handle_smart_coop_update(changed)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        api.get_smart_coop_logs.assert_awaited_once_with("coop-1")

    async def test_close_cancels_pending_log_refreshes(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        kerbl = KerblIOT(api, log_refresh_delay=60)
        kerbl._smart_coops["coop-1"] = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )
        kerbl._schedule_log_refresh("coop-1")
        first_task = kerbl._log_refresh_tasks["coop-1"]
        kerbl._schedule_log_refresh("coop-1")

        await kerbl.async_close()

        self.assertTrue(first_task.cancelled())
        self.assertEqual(kerbl._log_refresh_tasks, {})

    async def test_refresh_logs_ignores_unknown_smart_coop(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        kerbl = KerblIOT(api)

        logs = await kerbl.refresh_smart_coop_logs("unknown")

        self.assertEqual(logs, [])
        api.get_smart_coop_logs.assert_not_awaited()

    async def test_new_update_replacement_and_task_cancellation(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        kerbl = KerblIOT(api, log_refresh_delay=60)
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )
        await kerbl._handle_smart_coop_update(coop)
        first_task = kerbl._log_refresh_tasks["coop-1"]
        kerbl._schedule_log_refresh("coop-1")
        await asyncio.sleep(0)
        self.assertTrue(first_task.cancelled())
        await kerbl.async_close()

        task = asyncio.create_task(kerbl._refresh_logs_after_delay("coop-1"))
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_load_updates_existing_smart_coop_in_place(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        first = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "description": "Before", "isOnline": True}, api
        )
        updated = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "description": "After", "isOnline": True}, api
        )
        api.get_smart_coop_logs.return_value = []
        api.get_smart_coops.side_effect = [[first], [updated]]
        kerbl = KerblIOT(api)

        await kerbl.load()
        await kerbl.load()

        self.assertIs(kerbl.get_smart_coop("coop-1"), first)
        self.assertEqual(first.name, "After")

    def test_rejects_negative_log_refresh_delay(self) -> None:
        with self.assertRaises(ValueError):
            KerblIOT(AsyncMock(spec=KerblIOTApi), log_refresh_delay=-1)

    async def test_context_manager_logs_in_and_closes_api(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        api.get_smart_coops.return_value = []
        async with KerblIOT(api) as kerbl:
            self.assertEqual(kerbl.smart_coops, [])
        api.login.assert_awaited_once()
        api.close.assert_awaited_once()

    async def test_log_callbacks_and_background_refresh_failure(self) -> None:
        api = AsyncMock(spec=KerblIOTApi)
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )
        api.get_smart_coops.return_value = [coop]
        api.get_smart_coop_logs.return_value = []
        callback = AsyncMock()
        kerbl = KerblIOT(api, log_refresh_delay=0)
        kerbl.register_smart_coop_log_callback(callback)
        await kerbl.load()
        callback.assert_awaited_once_with(coop, [])
        api.get_smart_coop_logs.side_effect = RuntimeError("offline")
        await kerbl._refresh_logs_after_delay("coop-1")