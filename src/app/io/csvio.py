"""Helpers for reading and writing CSV files."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Dict, List


def read_csv(path: Path) -> List[Dict[str, str]]:
    """Read a CSV file ensuring values are strings."""

    rows: List[Dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({k: (v or "") for k, v in row.items()})
    return rows


def write_csv(
    path: Path,
    fieldnames: Iterable[str],
    rows: Iterable[Dict[str, str]],
    append: bool = False,
) -> bool:
    """Write *rows* to *path* using *fieldnames*.

    Returns ``True`` if the file was created, ``False`` otherwise.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    mode = "a" if append and exists else "w"
    with open(path, mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        if mode == "w" or not exists:
            writer.writeheader()
        writer.writerows(rows)
    return not exists


__all__ = ["read_csv", "write_csv"]
