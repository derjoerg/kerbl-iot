"""Models shared by multiple Kerbl IoT device types."""

from dataclasses import dataclass, fields, is_dataclass
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
