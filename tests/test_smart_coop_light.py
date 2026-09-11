"""Tests for the SmartCoop light component model."""

import unittest
from unittest.mock import AsyncMock, patch

from kerbl_iot.models.smart_coop import SmartCoop
from kerbl_iot.models.smart_coop_light import SmartCoopLight


class SmartCoopLightTest(unittest.IsolatedAsyncioTestCase):
    """Verify light component parsing."""

    def test_light_payload_is_parsed(self) -> None:
        light = SmartCoopLight.from_api(
            {
                "id": "light-1",
                "currentDimValue": 10,
                "eveningOnTime": 1,
                "morningOnTime": 2,
                "mode": 4,
                "darkTime": "10:00",
                "closingMode": 1,
            }
        )

        self.assertEqual(light.id, "light-1")
        self.assertEqual(light.current_dim_value, 10)
        self.assertTrue(light.is_on)
        self.assertEqual(light.dark_time, "10:00")
        self.assertEqual(
            light.to_diagnostics(),
            {
                "id": "light-1",
                "current_dim_value": 10,
                "is_on": True,
                "evening_on_time": 1,
                "morning_on_time": 2,
                "mode": 4,
                "dark_time": "10:00",
                "closing_mode": 1,
            },
        )

    def test_missing_dim_value_has_unknown_light_state(self) -> None:
        self.assertIsNone(SmartCoopLight.from_api(None).is_on)

    async def test_light_commands_delegate_to_attached_client(self) -> None:
        api = AsyncMock()
        api._press_light.return_value = "light-pressed"
        coop = SmartCoop.from_api({"id": "coop-1", "userId": "user-1", "isOnline": True}, api)

        self.assertEqual(await coop.light.press(), "light-pressed")
        api._press_light.assert_awaited_once_with("coop-1")

    async def test_turn_on_off_and_idempotent_target(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "isOnline": True,
                "light": {"currentDimValue": 0},
            },
            api,
        )
        with (
            patch.object(SmartCoop, "refresh_state", AsyncMock()),
            patch.object(SmartCoopLight, "wait_for_state", AsyncMock(return_value=coop)),
        ):
            self.assertEqual(await coop.light.turn_on(), coop)
            coop.light.current_dim_value = 100
            self.assertIs(await coop.light.turn_on(), coop)
            self.assertEqual(await coop.light.turn_off(), coop)

        self.assertEqual(api._press_light.await_count, 2)

    async def test_wait_and_unknown_state_errors(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api({"id": "coop-1", "userId": "user-1", "isOnline": True}, api)

        with self.assertRaises(TimeoutError):
            await coop.light.wait_for_state(True, timeout=0)
        with patch.object(SmartCoop, "refresh_state", AsyncMock()):
            with self.assertRaises(RuntimeError):
                await coop.light.turn_on()

    async def test_commands_require_an_attached_smart_coop(self) -> None:
        light = SmartCoopLight.from_api({"currentDimValue": 1})

        with self.assertRaisesRegex(RuntimeError, "not attached"):
            await light.press()
