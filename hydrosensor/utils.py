"""Utility functions for general use."""

import codecs
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


def checksum_int(s: str) -> int:
    """Calculate checksum of a string and return as integer."""
    total = sum(ord(c) for c in s)
    # return lower byte only as int
    return total & 0xFF


def checksum_hex_string(s: str) -> str:
    """Calculate checksum of a string and return as hexidecimal string."""
    sum_int = checksum_int(s)
    # return lower byte only as hex string
    return int_to_hex_string(sum_int)


def checksum_lower_byte(s: str, hex_check) -> bool:
    """Perform checksum on character byte values.

    Takes a string, sums the ASCII byte values of its characters,
    and returns the lower byte as an integer.
    """
    sum_int = checksum_int(s)
    # total = sum(ord(c) for c in s)
    # sum_hex = total & 0xFF
    return sum_int == int(hex_check, 16)


def encode_string(s: str) -> bytes:
    """Encode a string to hexidecimal bytes using UTF-8 encoding."""
    return codecs.encode(s.encode("utf-8"), "hex")


def decode_string(b: bytes) -> str:
    """Decode hexidecimal bytes to a string using UTF-8 encoding."""
    return codecs.decode(b, "hex").decode("utf-8")


def encode_string_to_message(s: str) -> str:
    """Encode a message string to hexidecimal bytes send command."""
    # prepend message with >F command for sending to satellite
    hex_msg = ">F" + encode_string(s).decode("utf-8")
    # calculate checksum of message and append to end
    checksum = checksum_hex_string(hex_msg[1:])  # exclude the '>' from checksum calculation
    full_msg = hex_msg + checksum
    return full_msg


def int_to_hex_string(i: int) -> str:
    """Convert an integer to a hexidecimal string."""
    hex_str = "{:X}".format(i)
    if len(hex_str) % 2 != 0:
        hex_str = "0" + hex_str
    return hex_str
