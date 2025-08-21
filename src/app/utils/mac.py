"""Utilities for working with MAC addresses."""
from __future__ import annotations

import re

MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}([-:][0-9A-Fa-f]{2}){5}$")


def normalize(mac: str) -> str:
    """Return *mac* in ``XX:XX:XX:XX:XX:XX`` format if valid.

    Non-hex characters are stripped and the result is upper-cased. If the
    cleaned value does not contain exactly 12 hex digits an empty string is
    returned.
    """

    cleaned = re.sub(r"[^0-9A-Fa-f]", "", mac or "")
    if len(cleaned) != 12:
        return ""
    parts = [cleaned[i : i + 2] for i in range(0, 12, 2)]
    return ":".join(parts).upper()


def is_valid(mac: str) -> bool:
    """Return ``True`` if *mac* looks like a valid MAC address."""

    return bool(MAC_RE.fullmatch(normalize(mac)))


__all__ = ["MAC_RE", "normalize", "is_valid"]
