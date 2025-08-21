"""Helpers for building report1.csv from verified and pending data."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def load_device_mapping(config_path: Path) -> List[Tuple[str, str]]:
    devices: List[Tuple[str, str]] = []
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


def read_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not path.exists():
        return rows
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({k: (v or "") for k, v in row.items()})
    return rows


def build_verified_rows(
    devices: List[Tuple[str, str]], rows: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    report_rows: List[Dict[str, str]] = []
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
                    "На пристрої ввімкнено генерацію випадкової MAC-адреси - "
                    f"{randmac_val}"
                )
            note = "\n".join(note_parts)
            report_rows.append(
                {
                    "source": row.get("source", ""),
                    "verified": "true",
                    "type": row.get("type", ""),
                    "name": name,
                    "ipmac": ipmac,
                    "note": note,
                }
            )
    return report_rows


def _format_dt(value: str) -> str:
    if not value:
        return ""
    value = value.strip()
    if value.isdigit():
        try:
            ts = int(value)
            if ts > 1_000_000_000_000:
                ts /= 1000
            dt = datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            return value
    else:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return value
    return dt.strftime("%d.%m.%Y %H:%M")


def build_pending_rows(
    devices: List[Tuple[str, str]], rows: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    report_rows: List[Dict[str, str]] = []
    for key, display_name in devices:
        for row in rows:
            if row.get("type") != key:
                continue
            name = f"{display_name}\n{row.get('name', '')}"
            ipmac = f"{row.get('ip', '')}\n{row.get('mac', '')}"
            note_parts = ["Не надано для перевірки."]
            first = row.get("firstDate", "")
            last = row.get("lastDate", "")
            if first and last:
                first_fmt = _format_dt(first)
                last_fmt = _format_dt(last)
                if first == last:
                    note_parts.append(
                        f"Перше та останнє підключення – {last_fmt}."
                    )
                else:
                    note_parts.append(
                        f"Перше підключення – {first_fmt}, останнє підключення – {last_fmt}."
                    )
            elif not first and last:
                last_fmt = _format_dt(last)
                note_parts.append(f"Останнє підключення – {last_fmt}.")
            note = "\n".join(note_parts)
            report_rows.append(
                {
                    "source": row.get("source", ""),
                    "verified": "false",
                    "type": row.get("type", ""),
                    "name": name,
                    "ipmac": ipmac,
                    "note": note,
                }
            )
    return report_rows


def write_report(rows: List[Dict[str, str]], path: Path) -> int:
    fieldnames = ["source", "verified", "type", "name", "ipmac", "note"]
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[Tuple[str, ...]] = set()
    file_exists = path.exists()
    if file_exists:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                existing.add(tuple(row.get(field, "") for field in fieldnames))
    mode = "a" if file_exists else "w"
    added = 0
    with open(path, mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            key = tuple(row.get(field, "") for field in fieldnames)
            if key in existing:
                continue
            writer.writerow(row)
            existing.add(key)
            added += 1
    return added


def generate_report(base_dir: Path) -> None:
    devices = load_device_mapping(base_dir / "configs" / "base.yaml")
    verified_path = base_dir / "data" / "interim" / "verified.csv"
    pending_path = base_dir / "data" / "interim" / "pending.csv"

    verified_rows = read_rows(verified_path)
    pending_rows = read_rows(pending_path)

    report_rows = build_verified_rows(devices, verified_rows)
    report_rows.extend(build_pending_rows(devices, pending_rows))
    report_path = base_dir / "data" / "interim" / "report1.csv"
    added = write_report(report_rows, report_path)
    print(f"Створено файл {report_path}")
    print(f"Додано {added} записів")


__all__ = [
    "load_device_mapping",
    "read_rows",
    "build_verified_rows",
    "build_pending_rows",
    "write_report",
    "generate_report",
]
