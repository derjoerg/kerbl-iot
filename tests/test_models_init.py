"""Tests for the model package public exports."""

import unittest

from kerbl_iot.models import (
    CommandResult,
    DoorState,
    SmartCoop,
    SmartCoopBrightness,
    SmartCoopDoor,
    SmartCoopFeeder,
    SmartCoopLight,
    SmartCoopLog,
    SmartCoopWaterHeater,
)
from kerbl_iot.models.base import CommandResult as BaseCommandResult
from kerbl_iot.models.door_state import DoorState as DoorStateModel
from kerbl_iot.models.smart_coop import SmartCoop as SmartCoopModel
from kerbl_iot.models.smart_coop_brightness import SmartCoopBrightness as SmartCoopBrightnessModel
from kerbl_iot.models.smart_coop_door import SmartCoopDoor as SmartCoopDoorModel
from kerbl_iot.models.smart_coop_feeder import SmartCoopFeeder as SmartCoopFeederModel
from kerbl_iot.models.smart_coop_light import SmartCoopLight as SmartCoopLightModel
from kerbl_iot.models.smart_coop_log import SmartCoopLog as SmartCoopLogModel
from kerbl_iot.models.smart_coop_water_heater import SmartCoopWaterHeater as SmartCoopWaterHeaterModel


class ModelPackageTest(unittest.TestCase):
    """Verify model package re-exports."""

    def test_re_exports_model_types(self) -> None:
        self.assertIs(CommandResult, BaseCommandResult)
        self.assertIs(DoorState, DoorStateModel)
        self.assertIs(SmartCoop, SmartCoopModel)
        self.assertIs(SmartCoopBrightness, SmartCoopBrightnessModel)
        self.assertIs(SmartCoopDoor, SmartCoopDoorModel)
        self.assertIs(SmartCoopFeeder, SmartCoopFeederModel)
        self.assertIs(SmartCoopLight, SmartCoopLightModel)
        self.assertIs(SmartCoopLog, SmartCoopLogModel)
        self.assertIs(SmartCoopWaterHeater, SmartCoopWaterHeaterModel)