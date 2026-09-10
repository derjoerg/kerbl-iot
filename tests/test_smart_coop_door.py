"""Tests for the SmartCoop door component model."""

import unittest
from unittest.mock import AsyncMock, patch

from kerbl_iot.models.door_state import DoorState
from kerbl_iot.models.smart_coop import SmartCoop
from kerbl_iot.models.smart_coop_door import SmartCoopDoor


class SmartCoopDoorTest(unittest.IsolatedAsyncioTestCase):
    """Verify door component parsing."""

    def test_door_payload_is_parsed(self) -> None:
        door = SmartCoopDoor.from_api(
            {
                "id": "door-1",
                "hasNoDoor": False,
                "state": 79,
                "doorClosesInMin": 6,
                "type": 2,
                "openingMode": 0,
                "relativeOpeningBrightness": 30,
                "openingTime": "08:00",
                "closingMode": 0,
                "relativeClosingBrightness": 15,
                "closingDelayDuration": 6,
                "weekendMode": 0,
                "weekendOpeningTime": "09:00",
            }
        )

        self.assertEqual(door.id, "door-1")
        self.assertFalse(door.has_no_door)
        self.assertIs(door.state, DoorState.OPEN)
        self.assertEqual(door.closes_in_minutes, 6)
        self.assertEqual(door.opening_time, "08:00")
        self.assertEqual(door.weekend_opening_time, "09:00")
        self.assertEqual(
            door.to_diagnostics(),
            {
                "id": "door-1",
                "has_no_door": False,
                "state": "OPEN",
                "state_value": 79,
                "closes_in_minutes": 6,
                "type": 2,
                "opening_mode": 0,
                "relative_opening_brightness": 30,
                "opening_time": "08:00",
                "closing_mode": 0,
                "relative_closing_brightness": 15,
                "closing_delay_duration": 6,
                "weekend_mode": 0,
                "weekend_opening_time": "09:00",
            },
        )

    def test_missing_door_payload_has_unknown_values(self) -> None:
        door = SmartCoopDoor.from_api(None)

        self.assertIsNone(door.id)
        self.assertIsNone(door.state)
        self.assertIsNone(door.to_diagnostics()["state"])

    async def test_door_commands_delegate_to_attached_client(self) -> None:
        api = AsyncMock()
        api._press_door.return_value = "door-pressed"
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )

        self.assertEqual(await coop.door.press(), "door-pressed")
        api._press_door.assert_awaited_once_with("coop-1")

    async def test_open_close_and_idempotent_target(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "isOnline": True,
                "door": {"state": 67},
            },
            api,
        )
        with (
            patch.object(SmartCoop, "refresh_state", AsyncMock()),
            patch.object(SmartCoopDoor, "wait_for_state", AsyncMock(return_value=coop)),
        ):
            self.assertEqual(await coop.door.open(), coop)
            coop.door.state = DoorState.OPEN
            self.assertIs(await coop.door.open(), coop)
            self.assertEqual(await coop.door.close(), coop)

        self.assertEqual(api._press_door.await_count, 2)

    async def test_wait_and_target_state_errors(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {"id": "coop-1", "userId": "user-1", "isOnline": True}, api
        )

        with self.assertRaises(TimeoutError):
            await coop.door.wait_for_state(DoorState.OPEN, timeout=0)
        with patch.object(SmartCoop, "refresh_state", AsyncMock()):
            coop.door.state = DoorState.OPENING
            with self.assertRaises(RuntimeError):
                await coop.door.close()

    async def test_commands_require_an_attached_smart_coop(self) -> None:
        door = SmartCoopDoor.from_api({"state": 79})

        with self.assertRaisesRegex(RuntimeError, "not attached"):
            await door.press()