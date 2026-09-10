"""Tests for the model package public exports."""

import unittest

from kerbl_iot.models import CommandResult, DoorState, SmartCoop, SmartCoopLog
from kerbl_iot.models.base import CommandResult as BaseCommandResult
from kerbl_iot.models.smart_coop import (
    DoorState as SmartCoopDoorState,
    SmartCoop as SmartCoopModel,
    SmartCoopLog as SmartCoopLogModel,
)


class ModelPackageTest(unittest.TestCase):
    """Verify model package re-exports."""

    def test_re_exports_model_types(self) -> None:
        self.assertIs(CommandResult, BaseCommandResult)
        self.assertIs(DoorState, SmartCoopDoorState)
        self.assertIs(SmartCoop, SmartCoopModel)
        self.assertIs(SmartCoopLog, SmartCoopLogModel)