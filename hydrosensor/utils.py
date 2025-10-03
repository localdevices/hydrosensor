"""Utility functions for general use."""

import enum
from typing import Any, Optional


class MsgStatus(enum.Enum):
    """Enum for status of a request Response."""

    OK = 1
    PENDING = 2
    ERROR = 9


class Response:
    """Response object describing status, value and message resulting from a request."""

    def __init__(self, status: MsgStatus, value: Optional[Any] = None, message: Optional[str] = None):
        """Initialize object."""
        self.status = status
        self.value = value
        self.message = message

    def __str__(self):
        """Return string representation of object."""
        return str(self.dict())

    def __repr__(self):
        """Return representation of object."""
        return self.__str__()

    def dict(self):
        """Return dictionary representation of object."""
        return self.__dict__


def checksum_lower_byte(s: str, hex_check) -> int:
    """Perform checksum on character byte values.

    Takes a string, sums the ASCII byte values of its characters,
    and returns the lower byte as an integer.
    """
    total = sum(ord(c) for c in s)
    sum_hex = total & 0xFF
    return sum_hex == int(hex_check, 16)
