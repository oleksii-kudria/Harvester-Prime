#!/usr/bin/env python3
"""Generate Mikrotik firewall rules and DHCP static lease commands."""
# ruff: noqa: E402
from __future__ import annotations

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from app.processors.mikrotik_firewall import build_firewall, read_rows


def main() -> None:
    verified_path = BASE_DIR / "data" / "interim" / "verified.csv"
    if not verified_path.exists():
        print(f"Файл {verified_path} не знайдено")
        sys.exit(1)

    rows = read_rows(verified_path)
    sources = sorted({row.get("source", "") for row in rows if row.get("source", "")})
    if not sources:
        print("Стовпець 'source' порожній")
        sys.exit(1)

    for idx, src in enumerate(sources, start=1):
        print(f"{idx}. {src}")
    try:
        choice = int(input("Оберіть джерело за номером: "))
        source_value = sources[choice - 1]
    except (ValueError, IndexError):
        print("Невірний вибір")
        sys.exit(1)

    result_dir = BASE_DIR / "data" / "result"
    out_path = result_dir / f"mikrotik-firewall-{source_value}.txt"
    build_firewall(source_value, verified_path, out_path)
    print(f"Створено файл {out_path}")


if __name__ == "__main__":
    main()
