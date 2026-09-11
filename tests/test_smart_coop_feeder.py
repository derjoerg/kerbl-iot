"""Tests for the SmartCoop feeder component model."""

import unittest
from unittest.mock import AsyncMock

from kerbl_iot.models.smart_coop import SmartCoop
from kerbl_iot.models.smart_coop_feeder import SmartCoopFeeder


class SmartCoopFeederTest(unittest.IsolatedAsyncioTestCase):
    """Verify feeder component parsing."""

    def test_feeder_payload_is_parsed(self) -> None:
        feeder = SmartCoopFeeder.from_api(
            {
                "id": "feeder-1",
                "startTime": "06:38",
                "endTime": "20:19",
                "feedingInterval": 41,
                "intervalStartTimes": '["06:38","07:19"]',
                "intervalEndTimes": '["07:18","07:59"]',
                "feedingLocked": False,
                "feedingActive": True,
                "hasFeedSensor": True,
                "isFeedFull": True,
                "feedingInProgress": False,
                "animalCount": 7,
                "amountPerAnimal": 100,
                "amountPerFeedingIntervals": "[0,1]",
            }
        )

        self.assertEqual(feeder.id, "feeder-1")
        self.assertEqual(feeder.start_time, "06:38")
        self.assertEqual(feeder.interval_start_times, ["06:38", "07:19"])
        self.assertEqual(feeder.interval_end_times, ["07:18", "07:59"])
        self.assertFalse(feeder.feeding_locked)
        self.assertTrue(feeder.feeding_active)
        self.assertTrue(feeder.has_feed_sensor)
        self.assertTrue(feeder.is_feed_full)
        self.assertFalse(feeder.feeding_in_progress)
        self.assertEqual(feeder.animal_count, 7)
        self.assertEqual(feeder.amount_per_animal, 100)
        self.assertEqual(feeder.amount_per_feeding_intervals, [0, 1])
        self.assertEqual(
            feeder.to_diagnostics(),
            {
                "id": "feeder-1",
                "start_time": "06:38",
                "end_time": "20:19",
                "feeding_interval": 41,
                "interval_start_times": ["06:38", "07:19"],
                "interval_end_times": ["07:18", "07:59"],
                "feeding_locked": False,
                "feeding_active": True,
                "has_feed_sensor": True,
                "is_feed_full": True,
                "feeding_in_progress": False,
                "animal_count": 7,
                "amount_per_animal": 100,
                "amount_per_feeding_intervals": [0, 1],
            },
        )

    def test_invalid_json_lists_are_unknown(self) -> None:
        feeder = SmartCoopFeeder.from_api(
            {
                "intervalStartTimes": "not-json",
                "intervalEndTimes": "[1]",
                "amountPerFeedingIntervals": '["1"]',
            }
        )

        self.assertIsNone(feeder.interval_start_times)
        self.assertIsNone(feeder.interval_end_times)
        self.assertIsNone(feeder.amount_per_feeding_intervals)

    def test_json_list_fields_accept_lists(self) -> None:
        feeder = SmartCoopFeeder.from_api(
            {
                "intervalStartTimes": ["06:38"],
                "intervalEndTimes": ["07:18"],
                "amountPerFeedingIntervals": [1],
            }
        )

        self.assertEqual(feeder.interval_start_times, ["06:38"])
        self.assertEqual(feeder.interval_end_times, ["07:18"])
        self.assertEqual(feeder.amount_per_feeding_intervals, [1])

    def test_feeder_updates_in_place(self) -> None:
        feeder = SmartCoopFeeder.from_api({"id": "before", "feedingInProgress": False})

        feeder.update_from_api(SmartCoopFeeder.from_api({"id": "after", "feedingInProgress": True}))

        self.assertEqual(feeder.id, "after")
        self.assertTrue(feeder.feeding_in_progress)

    def test_missing_json_lists_are_unknown(self) -> None:
        feeder = SmartCoopFeeder.from_api(None)

        self.assertIsNone(feeder.interval_start_times)
        self.assertIsNone(feeder.interval_end_times)
        self.assertIsNone(feeder.amount_per_feeding_intervals)

    def test_non_json_list_values_are_unknown(self) -> None:
        feeder = SmartCoopFeeder.from_api(
            {
                "intervalStartTimes": 1,
                "intervalEndTimes": object(),
                "amountPerFeedingIntervals": False,
            }
        )

        self.assertIsNone(feeder.interval_start_times)
        self.assertIsNone(feeder.interval_end_times)
        self.assertIsNone(feeder.amount_per_feeding_intervals)

    async def test_feeder_command_delegates_to_attached_client(self) -> None:
        api = AsyncMock()
        api._press_feeder.return_value = "feeder-pressed"
        coop = SmartCoop.from_api({"id": "coop-1", "userId": "user-1", "isOnline": True}, api)

        self.assertEqual(await coop.feeder.press(), "feeder-pressed")
        api._press_feeder.assert_awaited_once_with("coop-1")

    async def test_wait_uses_aggregate_update_event(self) -> None:
        api = AsyncMock()
        coop = SmartCoop.from_api(
            {
                "id": "coop-1",
                "userId": "user-1",
                "isOnline": True,
                "feeder": {"feedingInProgress": False},
            },
            api,
        )

        with self.assertRaises(TimeoutError):
            await coop.feeder.wait_for_state(True, timeout=0)

    async def test_commands_require_an_attached_smart_coop(self) -> None:
        feeder = SmartCoopFeeder.from_api({"feedingInProgress": False})

        with self.assertRaisesRegex(RuntimeError, "not attached"):
            await feeder.press()
