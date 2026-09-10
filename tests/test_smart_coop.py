"""Tests for SmartCoop models."""

import asyncio
import unittest
from unittest.mock import AsyncMock, call, patch

from kerbl_iot.models.smart_coop import DoorState, SmartCoop, SmartCoopLog


class SmartCoopTest(unittest.IsolatedAsyncioTestCase):
    """Verify SmartCoop parsing."""

    def test_closed_door_state_is_mapped_to_enum(self) -> None:
        coop = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "description": "Test coop",
                "isOnline": True,
                "door": {"state": 67},
                "light": {"currentDimValue": 1},
                "feeder": {"feedingInProgress": False},
            }
        )

        self.assertIs(coop.door_state, DoorState.CLOSED)
        self.assertEqual(coop.light_dim_value, 1)
        self.assertTrue(coop.light_is_on)
        self.assertFalse(coop.feeding_in_progress)

    def test_missing_light_value_has_unknown_light_state(self) -> None:
        coop = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "isOnline": True,
            }
        )

        self.assertIsNone(coop.light_is_on)

    async def test_device_commands_delegate_to_attached_client(self) -> None:
        api = AsyncMock()
        api._toggle_light.return_value = "command-result"
        api._toggle_feeder.return_value = "feeder-toggled"
        api._toggle_door.return_value = "door-toggled"
        api._wait_for_light_state.return_value = "light-state"
        api._wait_for_feeding_state.return_value = "feeding-state"
        api._wait_for_door_state.return_value = "door-state"
        api._acknowledge_errors.return_value = "acknowledged"
        coop = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "isOnline": True,
                "light": {"currentDimValue": 0},
            },
            api,
        )

        self.assertEqual(await coop.toggle_light(), "command-result")
        with (
            patch.object(SmartCoop, "refresh_state", AsyncMock()),
            patch.object(SmartCoop, "wait_for_light_state", AsyncMock(return_value="light-state")),
            patch.object(SmartCoop, "wait_for_feeding_state", AsyncMock(return_value="feeding-state")),
            patch.object(SmartCoop, "wait_for_door_state", AsyncMock(return_value="door-state")),
        ):
            self.assertEqual(await coop.turn_light_on(), "light-state")
            self.assertIs(await coop.turn_light_off(), coop)
            self.assertEqual(await coop.toggle_feeder(), "feeder-toggled")
            self.assertEqual(await coop.toggle_door(), "door-toggled")
            coop.door_state = DoorState.CLOSED
            self.assertEqual(await coop.open_door(), "door-state")
            coop.door_state = DoorState.OPEN
            self.assertEqual(await coop.close_door(), "door-state")
            self.assertEqual(await coop.acknowledge_errors([256]), "acknowledged")
            self.assertEqual(await coop.wait_for_light_state(True, timeout=5), "light-state")
            self.assertEqual(
                await coop.wait_for_feeding_state(True, timeout=5), "feeding-state"
            )
            self.assertEqual(
                await coop.wait_for_door_state(DoorState.OPEN, timeout=5), "door-state"
            )
        self.assertEqual(api._toggle_light.await_args_list, [call("coop-1"), call("coop-1")])
        api._toggle_feeder.assert_awaited_once_with("coop-1")
        self.assertEqual(api._toggle_door.await_count, 3)
        api._acknowledge_errors.assert_awaited_once_with("coop-1", [256])

    async def test_device_commands_require_an_attached_client(self) -> None:
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}
        )

        with self.assertRaisesRegex(RuntimeError, "not attached"):
            await coop.toggle_light()

    async def test_device_state_actions_and_callbacks(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True, "light": {"currentDimValue": 0}}, api
        )
        fresh = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True, "light": {"currentDimValue": 100}, "door": {"state": 79}, "feeder": {"feedingInProgress": True}}, api
        )
        api.get_smart_coops.return_value = [fresh]
        callback = unittest.mock.Mock()
        coop.register_callback(callback)
        await coop.refresh_state()
        self.assertTrue(coop.light_is_on)
        self.assertIs(coop.door_state, DoorState.OPEN)
        self.assertTrue(coop.feeding_in_progress)
        callback.assert_called_once()
        coop.remove_callback(callback)

        with patch.object(SmartCoop, "refresh_state", AsyncMock()), patch.object(SmartCoop, "wait_for_light_state", AsyncMock(return_value=coop)), patch.object(SmartCoop, "wait_for_door_state", AsyncMock(return_value=coop)):
            await coop.turn_light_off()
            await coop.toggle_feeder()
            await coop.acknowledge_errors([256])
            await coop.close_door()
        api._toggle_light.assert_awaited()
        api._toggle_feeder.assert_awaited_once_with("coop-1")
        api._acknowledge_errors.assert_awaited_once_with("coop-1", [256])
        api._toggle_door.assert_awaited_once_with("coop-1")

    async def test_waits_and_target_state_errors(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )
        with self.assertRaises(TimeoutError):
            await coop.wait_for_light_state(True, timeout=0)
        with self.assertRaises(TimeoutError):
            await coop.wait_for_feeding_state(True, timeout=0)
        with self.assertRaises(TimeoutError):
            await coop.wait_for_door_state(DoorState.OPEN, timeout=0)
        api.get_smart_coops.return_value = []
        with self.assertRaises(RuntimeError):
            await coop.refresh_state()
        with patch.object(SmartCoop, "refresh_state", AsyncMock()):
            with self.assertRaises(RuntimeError):
                await coop.turn_light_on()
            coop.door_state = DoorState.OPENING
            with self.assertRaises(RuntimeError):
                await coop.close_door()

    async def test_idempotent_targets_and_event_wait(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True, "light": {"currentDimValue": 100}, "door": {"state": 79}}, api
        )
        with patch.object(SmartCoop, "refresh_state", AsyncMock()):
            self.assertIs(await coop.turn_light_on(), coop)
            self.assertIs(await coop.open_door(), coop)
        updated = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True, "light": {"currentDimValue": 0}}, api
        )
        waiter = asyncio.create_task(coop.wait_for_light_state(False, timeout=1))
        await asyncio.sleep(0)
        await coop.update_from_api(updated)
        self.assertIs(await waiter, coop)

    def test_log_entry_is_parsed(self) -> None:
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

        self.assertEqual(log.error_code, 128)
        self.assertEqual(log.error_key, "errorReason.feedEmpty")
        self.assertEqual(log.error_message, "Futter leer")
        self.assertEqual(log.timestamp_display, "2026-09-09 07:23")
        self.assertIsNotNone(log.occurred_at)
        self.assertIsNotNone(log.received_at.tzinfo)
        self.assertTrue(log.active)

    def test_placeholder_log_timestamp_is_not_treated_as_valid(self) -> None:
        log = SmartCoopLog.from_api(
            {
                "time": "00:00",
                "date": "2000.00.09",
                "active": True,
                "errorReason": {
                    "plain": 256,
                    "i18nKey": "errorReason.batteryEmpty",
                },
                "level": "error",
            }
        )

        self.assertIsNone(log.occurred_at)
        self.assertEqual(log.timestamp_display, "Zeitpunkt unbekannt")
        self.assertEqual(log.date, "2000.00.09")
        self.assertEqual(log.time, "00:00")

    def test_invalid_log_timestamp_is_not_treated_as_valid(self) -> None:
        log = SmartCoopLog.from_api(
            {
                "time": "not-a-time",
                "date": "not-a-date",
                "active": True,
                "errorReason": {
                    "plain": 99999,
                    "i18nKey": "errorReason.unknown",
                },
                "level": "error",
            }
        )

        self.assertIsNone(log.occurred_at)
        self.assertEqual(log.error_message, "errorReason.unknown")
