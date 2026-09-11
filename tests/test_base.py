"""Tests for shared Kerbl IoT models."""

import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from kerbl_iot.models.base import CommandResult, dataclass_to_diagnostics


class ExampleState(Enum):
    READY = "ready"


@dataclass
class ExampleDiagnostics:
    state: ExampleState
    occurred_at: datetime
    values: list[int]
    metadata: dict[str, ExampleState]
    _private: str = "hidden"


class CommandResultTest(unittest.TestCase):
    """Verify shared command response parsing."""

    def test_is_parsed_from_api_response(self) -> None:
        result = CommandResult.from_api({"success": True, "commandCount": 42})

        self.assertTrue(result.success)
        self.assertEqual(result.command_count, 42)

    def test_dataclass_diagnostics_encode_nested_values(self) -> None:
        diagnostics = dataclass_to_diagnostics(
            ExampleDiagnostics(
                state=ExampleState.READY,
                occurred_at=datetime(2026, 9, 11, tzinfo=UTC),
                values=[1, 2],
                metadata={"state": ExampleState.READY},
            )
        )

        self.assertEqual(diagnostics["state"], "READY")
        self.assertEqual(diagnostics["occurred_at"], "2026-09-11T00:00:00+00:00")
        self.assertEqual(diagnostics["values"], [1, 2])
        self.assertEqual(diagnostics["metadata"], {"state": "READY"})
        self.assertNotIn("_private", diagnostics)
