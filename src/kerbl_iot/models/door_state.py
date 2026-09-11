"""Door state values reported by SmartCoop devices."""

from enum import IntEnum


class DoorState(IntEnum):
    """Door states reported by a SmartCoop."""

    UNKNOWN = 63
    SIMULATE = 83
    OPEN = 79
    CLOSING = 99
    CLOSED = 67
    OPENING = 111
    TOGGLE_MANUAL = 116
    UNLOCK = 85
    LOCK_UNTIL_TOMORROW = 84
    LOCK_PERMANENTLY = 80
