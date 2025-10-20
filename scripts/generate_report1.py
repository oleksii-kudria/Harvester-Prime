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


def load_informsystem_mapping() -> dict[str, str]:
    """Return mapping from note values to information system names."""

    mapping: dict[str, str] = {}
    config_path: Path | None = None
    for filename in ("local.yaml", "local.yml"):
        path = BASE_DIR / "configs" / filename
        if path.exists():
            config_path = path
            break

    if config_path is None:
        return mapping

    in_apps = False
    current_source: str | None = None
    with open(config_path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.rstrip("\n")
            if not in_apps:
                if stripped.strip() == "apps:":
                    in_apps = True
                continue

            if not stripped.strip():
                continue

            if not stripped.startswith("  "):
                if in_apps:
                    break
                continue

            if stripped.startswith("    "):
                key, _, raw_value = stripped.strip().partition(":")
                value = raw_value.strip().strip('"\'')
                if key == "source":
                    current_source = value
                elif key == "target" and current_source is not None:
                    mapping[current_source.lower()] = value
                    if value:
                        mapping[value.lower()] = value
            else:
                current_source = None
                continue

    return mapping


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
    informsystem_mapping: dict[str, str],
) -> list[dict[str, str]]:
    """Create report rows for verified devices ordered by device keys."""
    report_rows: list[dict[str, str]] = []
    for key, display_name in devices:
        for row in rows:
            if row.get("type") != key:
                continue
            name_parts = [display_name, row.get("name", "")]
            note_val = row.get("note", "")
            informsystem, remaining_note = _extract_informsystem(
                note_val, informsystem_mapping
            )
            if remaining_note:
                name_parts.append(remaining_note)
            informsystem_value = informsystem or "none"
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
                    "informsystem": informsystem_value,
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
                    "informsystem": "none",
                }
            )
    return report_rows


def _extract_informsystem(
    note: str, mapping: dict[str, str]
) -> tuple[str, str]:
    """Return informsystem value and remaining note for *note* using *mapping*."""

    note = note or ""
    normalized = note.replace("\r\n", "\n").replace("\r", "\n")
    parts = [part.strip() for part in normalized.split("\n") if part.strip()]

    if not parts:
        return "", ""

    matched_values: list[str] = []
    matched_keys: set[str] = set()
    unmatched_parts: list[str] = []
    matched_any = False

    for part in parts:
        key = part.lower()
        target = mapping.get(key)
        if target is not None:
            matched_any = True
            target = target.strip()
            if target:
                normalized_target = target
                target_key = normalized_target.lower()
                if target_key not in matched_keys:
                    matched_keys.add(target_key)
                    matched_values.append(normalized_target)
        else:
            unmatched_parts.append(part)

    if not matched_any:
        return "", note

    remaining_note = "\n".join(unmatched_parts)
    informsystem_value = "\n".join(matched_values)
    return informsystem_value, remaining_note


def write_report(rows: list[dict[str, str]], path: Path) -> tuple[int, int]:
    """Write *rows* to CSV at *path* and track informsystem changes.

    Returns a tuple ``(written_rows, informsystem_updates)`` where
    ``written_rows`` is the number of rows written to the file and
    ``informsystem_updates`` is the number of rows where the ``informsystem``
    value was updated or newly populated with a meaningful value (i.e. not
    ``"none"``).
    """

    fieldnames = [
        "source",
        "verified",
        "ownership",
        "informsystem",
        "type",
        "name",
        "ipmac",
        "note",
        "firstConnect",
        "lastConnect",
        "firstConnectEpoch",
        "lastConnectEpoch",
    ]
    identifier_fields = ["source", "type", "name", "ipmac"]

    path.parent.mkdir(parents=True, exist_ok=True)

    existing_rows: list[dict[str, str]] = []
    existing_lookup: dict[tuple[str, ...], dict[str, str]] = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            existing_rows = list(reader)
        for row in existing_rows:
            key = tuple(row.get(field, "") for field in identifier_fields)
            existing_lookup[key] = row

    def _normalize_informsystem(value: str) -> str:
        return (value or "").strip()

    def _has_meaningful_informsystem(value: str) -> bool:
        normalized = _normalize_informsystem(value).lower()
        return bool(normalized) and normalized != "none"

    informsystem_updates = 0
    for row in rows:
        key = tuple(row.get(field, "") for field in identifier_fields)
        existing_row = existing_lookup.get(key)
        new_value = row.get("informsystem", "")
        if existing_row is None:
            if _has_meaningful_informsystem(new_value):
                informsystem_updates += 1
            continue

        existing_value = existing_row.get("informsystem", "")
        existing_meaningful = _has_meaningful_informsystem(existing_value)
        new_meaningful = _has_meaningful_informsystem(new_value)
        if existing_meaningful != new_meaningful:
            informsystem_updates += 1
        elif new_meaningful and _normalize_informsystem(existing_value) != _normalize_informsystem(new_value):
            informsystem_updates += 1

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            normalized = {field: row.get(field, "") for field in fieldnames}
            writer.writerow(normalized)

    return len(rows), informsystem_updates


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

    informsystem_mapping = load_informsystem_mapping()
    report_rows = build_verified_rows(
        devices, verified_rows, randomized_macs, informsystem_mapping
    )
    report_rows.extend(build_pending_rows(devices, pending_rows, randomized_macs))
    report_path = BASE_DIR / "data" / "result" / "report1.csv"
    written, informsystem_updates = write_report(report_rows, report_path)
    print(f"Створено файл {report_path}")
    print(f"Записано {written} записів")
    print(
        "Оновлено або створено значення informsystem у "
        f"{informsystem_updates} записах"
    )


if __name__ == "__main__":
    main()
