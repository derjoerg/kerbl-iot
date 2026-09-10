"""Tests for shared Kerbl IoT models."""

import unittest

from kerbl_iot.models.base import CommandResult


class CommandResultTest(unittest.TestCase):
    """Verify shared command response parsing."""

    def test_is_parsed_from_api_response(self) -> None:
        result = CommandResult.from_api({"success": True, "commandCount": 42})

        self.assertTrue(result.success)
        self.assertEqual(result.command_count, 42)
