"""Tests for SmartCoop door state values."""

import unittest

from kerbl_iot.models.door_state import DoorState


class DoorStateTest(unittest.TestCase):
    """Verify known SmartCoop door state values."""

    def test_known_door_states_are_mapped(self) -> None:
        self.assertIs(DoorState(79), DoorState.OPEN)
        self.assertIs(DoorState(67), DoorState.CLOSED)
        self.assertIs(DoorState(111), DoorState.OPENING)
        self.assertIs(DoorState(99), DoorState.CLOSING)
