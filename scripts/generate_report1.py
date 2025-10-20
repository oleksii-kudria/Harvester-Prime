#!/usr/bin/env python3
"""Generate report1.csv from verified and pending CSV files using device mappings."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EXCLUDED_RANDOMIZED_TYPES = {"rarm", "rmkp"}
SPECIAL_NOTE_TYPES = {"rmkp", "rarm"}


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


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read CSV ensuring all fields are strings."""
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({k: (v or "") for k, v in row.items()})
    return rows


def build_verified_rows(
    devices: list[tuple[str, str]],
    rows: list[dict[str, str]],
    randomized_macs: set[str],
) -> list[dict[str, str]]:
    """Create report rows for verified devices ordered by device keys."""
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
            if key in SPECIAL_NOTE_TYPES:
                note_parts = [
                    "Не додавати до додатку 1.",
                    "Надано на перевірку.",
                    "На пристрої ввімкнено генерацію випадкової MAC-адреси",
                ]
            else:
                note_parts = ["Надано на перевірку."]
                randmac_val = row.get("randmac", "")
                if randmac_val:
                    note_parts.append(
                        "На пристрої ввімкнено генерацію випадкової MAC-адреси"
                        f" - {randmac_val}"
                    )
                if (
                    row.get("mac", "").upper() in randomized_macs
                    and key not in EXCLUDED_RANDOMIZED_TYPES
                ):
                    note_parts.insert(
                        1, "На пристрої увімкнена генерація випадкової MAC-адреси."
                    )

            note = "\n".join(note_parts)

            first_fmt, first_epoch = _parse_timestamp(row.get("firstDate", ""))
            last_fmt, last_epoch = _parse_timestamp(row.get("lastDate", ""))

            personal_val = row.get("personal", "").strip().lower()
            ownership = ""
            if personal_val == "true":
                suffix = "Пристрій особистий."
                ownership = "особистий"
            elif personal_val == "false":
                suffix = "Пристрій службовий."
                ownership = "службовий"
            else:
                suffix = ""

            if suffix:
                if note.endswith("\n"):
                    note += suffix
                elif note.endswith("."):
                    note += f" {suffix}"
                elif note:
                    note += f". {suffix}"
                else:
                    note = suffix
                note += " Заявка на підключення до локальних мереж, складена, МАС-адреса закріплена за ІР-адресою."
            report_rows.append(
                {
                    "source": row.get("source", ""),
                    "verified": "true",
                    "type": row.get("type", ""),
                    "name": name,
                    "ipmac": ipmac,
                    "note": note,
                    "firstConnect": first_fmt,
                    "lastConnect": last_fmt,
                    "firstConnectEpoch": first_epoch,
                    "lastConnectEpoch": last_epoch,
                    "ownership": ownership,
                }
            )
    return report_rows


def _parse_timestamp(value: str) -> tuple[str, str]:
    """Return formatted (``dd.MM.yyyy HH:mm``) and epoch strings for *value*.

    When parsing fails the original, stripped value is returned for both
    formatted and epoch representations to preserve the input data.
    """

    if not value:
        return "", ""

    stripped = value.strip()
    dt: datetime | None = None
    epoch_value: str = stripped

    if stripped.isdigit():
        try:
            ts = int(stripped)
            if ts > 1_000_000_000_000:  # milliseconds
                ts /= 1000
            dt = datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            return stripped, stripped
    else:
        try:
            dt = datetime.fromisoformat(stripped)
        except ValueError:
            return stripped, stripped

    if dt is None:
        return stripped, stripped

    epoch_value = str(int(dt.timestamp()))
    formatted_value = dt.strftime("%d.%m.%Y %H:%M")
    return formatted_value, epoch_value


def build_pending_rows(
    devices: list[tuple[str, str]],
    rows: list[dict[str, str]],
    randomized_macs: set[str],
) -> list[dict[str, str]]:
    """Create report rows for pending devices ordered by device keys."""
    report_rows: list[dict[str, str]] = []
    for key, display_name in devices:
        for row in rows:
            if row.get("type") != key:
                continue
            name = f"{display_name}\n{row.get('name', '')}"
            ipmac = f"{row.get('ip', '')}\n{row.get('mac', '')}"
            note_parts: list[str]
            if key in SPECIAL_NOTE_TYPES:
                note_parts = [
                    "Не додавати до додатку 1.",
                    "Надано на перевірку.",
                    "На пристрої ввімкнено генерацію випадкової MAC-адреси",
                ]
            else:
                note_parts = ["Не надано для перевірки."]
            first = row.get("firstDate", "")
            last = row.get("lastDate", "")
            first_fmt, first_epoch = _parse_timestamp(first)
            last_fmt, last_epoch = _parse_timestamp(last)
            if first and last:
                if first == last:
                    note_parts.append(
                        f"Перше та останнє підключення – {last_fmt}."
                    )
                else:
                    note_parts.append(
                        f"Перше підключення – {first_fmt}, останнє підключення – {last_fmt}."
                    )
            elif not first and last:
                note_parts.append(f"Останнє підключення – {last_fmt}.")
            if (
                row.get("mac", "").upper() in randomized_macs
                and key not in EXCLUDED_RANDOMIZED_TYPES
                and key not in SPECIAL_NOTE_TYPES
            ):
                note_parts.insert(
                    1, "На пристрої увімкнена генерація випадкової MAC-адреси."
                )

            note = "\n".join(note_parts)
            report_rows.append(
                {
                    "source": row.get("source", ""),
                    "verified": "false",
                    "type": row.get("type", ""),
                    "name": name,
                    "ipmac": ipmac,
                    "note": note,
                    "firstConnect": first_fmt if first else "",
                    "lastConnect": last_fmt if last else "",
                    "firstConnectEpoch": first_epoch if first else "",
                    "lastConnectEpoch": last_epoch if last else "",
                    "ownership": "none",
                }
            )
    return report_rows


def write_report(rows: list[dict[str, str]], path: Path) -> int:
    """Write rows to CSV at *path* with required columns.

    Returns the number of newly written rows. Rows that already exist in the
    target file are skipped.
    """

    fieldnames = [
        "source",
        "verified",
        "ownership",
        "type",
        "name",
        "ipmac",
        "note",
        "firstConnect",
        "lastConnect",
        "firstConnectEpoch",
        "lastConnectEpoch",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: set[tuple[str, ...]] = set()
    existing_rows: list[dict[str, str]] = []
    file_exists = path.exists()
    rewrite_required = False
    if file_exists:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            existing_rows = list(reader)
            header_fields = reader.fieldnames or []
            rewrite_required = any(field not in header_fields for field in fieldnames)
            for row in existing_rows:
                existing.add(tuple(row.get(field, "") for field in fieldnames))

    mode = "a" if file_exists and not rewrite_required else "w"
    added = 0
    with open(path, mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not file_exists or rewrite_required:
            writer.writeheader()
            if rewrite_required:
                for row in existing_rows:
                    normalized = {field: row.get(field, "") for field in fieldnames}
                    writer.writerow(normalized)
        for row in rows:
            key = tuple(row.get(field, "") for field in fieldnames)
            if key in existing:
                continue
            writer.writerow(row)
            existing.add(key)
            added += 1
    return added


def main() -> None:
    devices = load_device_mapping()
    verified_path = BASE_DIR / "data" / "interim" / "verified.csv"
    pending_path = BASE_DIR / "data" / "interim" / "pending.csv"
    dhcp_path = BASE_DIR / "data" / "interim" / "dhcp.csv"

    randomized_macs: set[str] = set()
    if dhcp_path.exists():
        for row in read_rows(dhcp_path):
            mac = row.get("mac", "").upper()
            randomized = row.get("randomized", "").strip().lower()
            if mac and randomized == "true":
                randomized_macs.add(mac)

    if verified_path.exists():
        verified_rows = read_rows(verified_path)
    else:
        print(f"Файл {verified_path} не знайдено")
        verified_rows = []

    if pending_path.exists():
        pending_rows = read_rows(pending_path)
    else:
        print(f"Файл {pending_path} не знайдено")
        pending_rows = []

    report_rows = build_verified_rows(devices, verified_rows, randomized_macs)
    report_rows.extend(build_pending_rows(devices, pending_rows, randomized_macs))
    report_path = BASE_DIR / "data" / "result" / "report1.csv"
    added = write_report(report_rows, report_path)
    print(f"Створено файл {report_path}")
    print(f"Додано {added} записів")


if __name__ == "__main__":
    main()
