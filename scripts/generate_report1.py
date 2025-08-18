#!/usr/bin/env python3
"""Generate report1.csv from verified.csv using device mappings."""
from __future__ import annotations

import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_device_mapping() -> list[tuple[str, str]]:
    """Return list of (key, name) preserving order from base.yaml.

    This function only parses the ``devices`` section of the YAML file and
    therefore avoids the need for external YAML libraries.
    """
    config_path = BASE_DIR / "configs" / "base.yaml"
    devices: list[tuple[str, str]] = []
    in_section = False
    with open(config_path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.rstrip()
            if not in_section:
                if stripped.strip() == "devices:":
                    in_section = True
                continue
            if not stripped.startswith("  ") or not stripped.strip():
                if in_section and stripped and not stripped.startswith("  "):
                    break
                continue
            key, _, value = stripped.strip().partition(":")
            devices.append((key, value.strip().strip('"\'')))
    return devices


def read_verified_rows(path: Path) -> list[dict[str, str]]:
    """Read verified.csv ensuring all fields are strings."""
    rows: list[dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({k: (v or "") for k, v in row.items()})
    return rows


def build_report_rows(devices: list[tuple[str, str]], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Create report rows ordered by device keys."""
    report_rows: list[dict[str, str]] = []
    for key, display_name in devices:
        for row in rows:
            if row.get("type") != key:
                continue
            name_parts = [display_name, row.get("name", "")]
            note_val = row.get("note", "")
            if note_val:
                name_parts.append(note_val)
            name = "\n".join(name_parts)
            ipmac = f"{row.get('ip', '')}\n{row.get('mac', '')}"
            note_parts = ["Надано на перевірку."]
            randmac_val = row.get("randmac", "")
            if randmac_val:
                note_parts.append(
                    f"На пристрої ввімкнено генерацію випадкової MAC-адреси - {randmac_val}"
                )
            note = "\n".join(note_parts)
            report_rows.append(
                {
                    "source": row.get("source", ""),
                    "type": row.get("type", ""),
                    "name": name,
                    "ipmac": ipmac,
                    "note": note,
                }
            )
    return report_rows


def write_report(rows: list[dict[str, str]], path: Path) -> None:
    """Write rows to CSV at *path* with required columns."""
    fieldnames = ["source", "type", "name", "ipmac", "note"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    devices = load_device_mapping()
    verified_path = BASE_DIR / "data" / "interim" / "verified.csv"
    rows = read_verified_rows(verified_path)
    report_rows = build_report_rows(devices, rows)
    report_path = BASE_DIR / "data" / "interim" / "report1.csv"
    write_report(report_rows, report_path)
    print(f"Створено файл {report_path}")
    print(f"Додано {len(report_rows)} записів")


if __name__ == "__main__":
    main()
