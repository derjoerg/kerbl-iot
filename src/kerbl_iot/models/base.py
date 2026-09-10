"""Models shared by multiple Kerbl IoT device types."""

from dataclasses import dataclass
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
