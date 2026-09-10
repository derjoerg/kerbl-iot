"""Tests for the SmartCoop water heater component model."""

import unittest

from kerbl_iot.models.smart_coop_water_heater import SmartCoopWaterHeater


class SmartCoopWaterHeaterTest(unittest.TestCase):
    """Verify water heater component parsing."""

    def test_water_heater_payload_is_parsed(self) -> None:
        water_heater = SmartCoopWaterHeater.from_api(
            {
                "id": "water-1",
                "waterTemperature": 17.6,
                "waterSensorState": True,
                "hasWaterSensor": True,
            }
        )

        self.assertEqual(water_heater.id, "water-1")
        self.assertEqual(water_heater.water_temperature, 17.6)
        self.assertTrue(water_heater.water_sensor_state)
        self.assertTrue(water_heater.has_water_sensor)
        self.assertTrue(water_heater.has_temperature_reading)
        self.assertEqual(
            water_heater.to_diagnostics(),
            {
                "id": "water-1",
                "water_temperature": 17.6,
                "water_sensor_state": True,
                "has_water_sensor": True,
                "has_temperature_reading": True,
            },
        )

    def test_water_heater_updates_in_place(self) -> None:
        water_heater = SmartCoopWaterHeater.from_api({"waterTemperature": 10.0})

        water_heater.update_from_api(
            SmartCoopWaterHeater.from_api({"waterTemperature": 11.5})
        )

        self.assertEqual(water_heater.water_temperature, 11.5)