"""Tests for the SmartCoop brightness component model."""

import unittest

from kerbl_iot.models.smart_coop_brightness import SmartCoopBrightness


class SmartCoopBrightnessTest(unittest.TestCase):
    """Verify brightness component parsing."""

    def test_brightness_payload_is_parsed(self) -> None:
        brightness = SmartCoopBrightness.from_api(
            {
                "id": "brightness-1",
                "externalSensorConnected": True,
                "currentBrightness": 56,
                "nightDurationStartTime": 72279,
                "nightDurationEndTime": 23884,
            }
        )

        self.assertEqual(brightness.id, "brightness-1")
        self.assertTrue(brightness.external_sensor_connected)
        self.assertEqual(brightness.current_brightness, 56)
        self.assertEqual(brightness.night_duration_start_time, 72279)
        self.assertTrue(brightness.is_available)

    def test_brightness_updates_in_place(self) -> None:
        brightness = SmartCoopBrightness.from_api({"currentBrightness": 10})

        brightness.update_from_api(SmartCoopBrightness.from_api({"currentBrightness": 20}))

        self.assertEqual(brightness.current_brightness, 20)