#!/usr/bin/env python3
"""Generate report1.csv from verified and pending CSV files."""
# ruff: noqa: E402
from __future__ import annotations

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from app.processors.report1 import generate_report


def main() -> None:
    generate_report(BASE_DIR)


if __name__ == "__main__":
    main()
