"""Utilities for handling note normalization."""
from __future__ import annotations

from typing import Dict

from app.config.loader import note_mapping


def normalize_note(note: str) -> str:
    """Return *note* replaced according to configuration mapping."""

    mapping: Dict[str, str] = note_mapping()
    key = (note or "").strip().lower()
    return mapping.get(key, note)


__all__ = ["normalize_note"]
