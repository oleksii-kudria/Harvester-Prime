"""Tools for removing interim CSV files."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import glob


def clean_interim(
    pattern: str = "data/interim/*.csv", exclude_suffix: str = ".example.csv"
) -> Iterable[str]:
    """Remove interim CSV files matching *pattern* except those ending with *exclude_suffix*.

    Yields paths of the removed files.
    """

    removed: list[str] = []
    for name in glob.glob(pattern):
        path = Path(name)
        if path.name.endswith(exclude_suffix):
            continue
        try:
            path.unlink()
            removed.append(str(path))
        except FileNotFoundError:
            continue
    return removed


__all__ = ["clean_interim"]
