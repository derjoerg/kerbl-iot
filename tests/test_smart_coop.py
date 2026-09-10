"""Tests for SmartCoop models."""

import asyncio
import unittest
from unittest.mock import AsyncMock

from kerbl_iot.models.door_state import DoorState
from kerbl_iot.models.smart_coop import SmartCoop


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

        self.assertIs(coop.door.state, DoorState.CLOSED)
        self.assertEqual(coop.light.current_dim_value, 1)
        self.assertTrue(coop.light.is_on)
        self.assertFalse(coop.feeder.feeding_in_progress)

    def test_real_device_payload_shape_is_parsed(self) -> None:
        coop = SmartCoop.from_api(
            {
                "id": "852e1e85-aa03-4121-8dfb-2ccedec1bd58",
                "userId": "dad94be9-1e68-4a6b-9c46-070fe53f99ee",
                "description": "H\u00fchnerstall",
                "firmwareVersion": "V01.34",
                "isOnline": True,
                "airTemperature": 22.5,
                "currentErrorReason": "[0]",
                "errorReasonHistory": "[]",
                "door": {"state": 79},
                "feeder": {
                    "feedingLocked": False,
                    "feedingActive": True,
                    "feedingInProgress": False,
                },
                "waterHeater": {"waterTemperature": 17.6},
                "light": {"currentDimValue": 0},
                "brightness": {"currentBrightness": 56},
                "power": {"currentVoltage": 12.226},
            }
        )

        self.assertEqual(coop.id, "852e1e85-aa03-4121-8dfb-2ccedec1bd58")
        self.assertEqual(coop.user_id, "dad94be9-1e68-4a6b-9c46-070fe53f99ee")
        self.assertEqual(coop.name, "H\u00fchnerstall")
        self.assertTrue(coop.online)
        self.assertEqual(coop.firmware_version, "V01.34")
        self.assertEqual(coop.air_temperature, 22.5)
        self.assertIs(coop.door.state, DoorState.OPEN)
        self.assertEqual(coop.water_heater.water_temperature, 17.6)
        self.assertEqual(coop.light.current_dim_value, 0)
        self.assertFalse(coop.light.is_on)
        self.assertFalse(coop.feeder.feeding_in_progress)
        self.assertTrue(coop.feeder.feeding_active)
        self.assertFalse(coop.feeder.feeding_locked)
        self.assertEqual(coop.brightness.current_brightness, 56)
        self.assertEqual(coop.current_error_reason, "[0]")
        self.assertEqual(coop.error_reason_history, "[]")

    def test_missing_light_value_has_unknown_light_state(self) -> None:
        coop = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "isOnline": True,
            }
        )

        self.assertIsNone(coop.light.is_on)

    async def test_error_acknowledgement_delegates_to_attached_client(self) -> None:
        api = AsyncMock()
        api._acknowledge_errors.return_value = "acknowledged"
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )

        self.assertEqual(await coop.acknowledge_errors([256]), "acknowledged")
        api._acknowledge_errors.assert_awaited_once_with("coop-1", [256])

    async def test_aggregate_actions_require_an_attached_client(self) -> None:
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}
        )

        with self.assertRaisesRegex(RuntimeError, "not attached"):
            await coop.acknowledge_errors([256])

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
        self.assertTrue(coop.light.is_on)
        self.assertIs(coop.door.state, DoorState.OPEN)
        self.assertTrue(coop.feeder.feeding_in_progress)
        callback.assert_called_once()
        coop.remove_callback(callback)
        self.assertIs(coop.door, coop.door)

    async def test_refresh_errors_when_device_disappears(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )
        api.get_smart_coops.return_value = []

        with self.assertRaises(RuntimeError):
            await coop.refresh_state()

    async def test_update_keeps_component_references(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True, "light": {"currentDimValue": 100}, "door": {"state": 79}}, api
        )
        light = coop.light
        door = coop.door
        updated = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True, "light": {"currentDimValue": 0}}, api
        )

        await coop.update_from_api(updated)

        self.assertIs(coop.light, light)
        self.assertIs(coop.door, door)
        self.assertFalse(coop.light.is_on)
        self.assertIsNone(coop.door.state)

    async def test_component_waits_use_aggregate_update_event(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True, "light": {"currentDimValue": 100}}, api
        )
        updated = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True, "light": {"currentDimValue": 0}}, api
        )
        waiter = asyncio.create_task(coop.light.wait_for_state(False, timeout=1))
        await asyncio.sleep(0)
        await coop.update_from_api(updated)
        self.assertIs(await waiter, coop)
