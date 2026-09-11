"""Models shared by multiple Kerbl IoT device types."""

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Result returned after sending a command to a Kerbl IoT device."""

    success: bool
    command_count: int | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "CommandResult":
        """Create a command result from an API response."""
        return cls(
            success=bool(data.get("success")),
            command_count=data.get("commandCount"),
        )


def copy_dataclass_fields(target: Any, source: Any) -> None:
    """Copy scalar public dataclass fields from source to target in place."""
    for field in fields(source):
        if field.name.startswith("_"):
            continue
        value = getattr(source, field.name)
        if is_dataclass(value):
            continue
        setattr(target, field.name, value)


def dataclass_to_diagnostics(instance: Any) -> dict[str, Any]:
    """Convert public dataclass fields to JSON-compatible diagnostics."""
    return {
        field.name: _diagnostic_value(getattr(instance, field.name))
        for field in fields(instance)
        if not field.name.startswith("_")
    }


def _diagnostic_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return dataclass_to_diagnostics(value)
    if isinstance(value, list):
        return [_diagnostic_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _diagnostic_value(item) for key, item in value.items()}
    return value
