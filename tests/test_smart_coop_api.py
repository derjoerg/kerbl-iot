"""Tests for the SmartCoop API protocol module."""

import unittest

from kerbl_iot.models.smart_coop_api import SmartCoopApi


class SmartCoopApiTest(unittest.TestCase):
    """Verify the protocol is importable from its own module."""

    def test_protocol_is_importable(self) -> None:
        self.assertEqual(SmartCoopApi.__name__, "SmartCoopApi")
