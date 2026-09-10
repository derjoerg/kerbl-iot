"""Tests for SmartCoop log entries."""

import unittest

from kerbl_iot.models.smart_coop_log import SmartCoopLog


class SmartCoopLogTest(unittest.TestCase):
    """Verify SmartCoop log parsing."""

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