"""Utilities for working with verified device records."""
from __future__ import annotations

from pathlib import Path
import csv
import re
from typing import Dict, List

from app.collectors.files import list_csv_files, write_csv


def _normalize_mac(value: str) -> str:
    """Return *value* normalised for comparison.

    The result uses upper-case letters and ``:`` separators with any
    whitespace removed. Non-hex characters are stripped.
    """

    hex_only = re.sub(r"[^0-9A-Fa-f]", "", value or "").upper()
    if len(hex_only) != 12:
        return ""
    return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2))


def append_other_to_verified(
    other_dir: Path, dhcp_file: Path, verified_file: Path
) -> None:
    """Append devices from ``other_dir`` matched with DHCP data.

    Rows from ``other_dir`` are matched to ``dhcp_file`` by MAC address.
    New rows are appended to ``verified_file`` while avoiding duplicates.
    """

    other_dir = Path(other_dir)
    dhcp_file = Path(dhcp_file)
    verified_file = Path(verified_file)

    other_files = list_csv_files(other_dir)
    if not other_files:
        print(f"Відсутні файли у {other_dir}. Крок додавання other пропущено.")
        return
    if not dhcp_file.exists():
        print(f"Файл {dhcp_file} не знайдено. Крок додавання other пропущено.")
        return

    # Build MAC index from DHCP file
    dhcp_index: Dict[str, Dict[str, str]] = {}
    try:
        with open(dhcp_file, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                mac = _normalize_mac(row.get("mac", ""))
                if mac:
                    dhcp_index[mac] = row
    except csv.Error as exc:  # pragma: no cover - unlikely
        print(f"Помилка читання {dhcp_file}: {exc}")
        return

    # Load existing entries from verified file
    existing_keys: set[tuple[str, str, str, str]] = set()
    if verified_file.exists():
        try:
            with open(verified_file, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    key = (
                        row.get("type", ""),
                        row.get("source", ""),
                        row.get("ip", ""),
                        _normalize_mac(row.get("mac", "")),
                    )
                    existing_keys.add(key)
        except csv.Error as exc:  # pragma: no cover - unlikely
            print(f"Помилка читання {verified_file}: {exc}")
            return

    fieldnames = [
        "type",
        "source",
        "name",
        "ip",
        "mac",
        "randmac",
        "owner",
        "note",
        "firstDate",
        "lastDate",
    ]

    new_rows: List[Dict[str, str]] = []
    match_count = 0
    dup_count = 0

    for path in other_files:
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    mac = _normalize_mac(row.get("mac", ""))
                    if not mac:
                        continue
                    dhcp_row = dhcp_index.get(mac)
                    if not dhcp_row:
                        continue
                    match_count += 1
                    out_row = {
                        "type": row.get("type", ""),
                        "source": dhcp_row.get("source", ""),
                        "name": row.get("name", ""),
                        "ip": dhcp_row.get("ip", ""),
                        "mac": dhcp_row.get("mac", ""),
                        "randmac": "",
                        "owner": "",
                        "note": "",
                        "firstDate": dhcp_row.get("firstDate", ""),
                        "lastDate": dhcp_row.get("lastDate", ""),
                    }
                    key = (
                        out_row["type"],
                        out_row["source"],
                        out_row["ip"],
                        mac,
                    )
                    if key in existing_keys:
                        dup_count += 1
                        continue
                    existing_keys.add(key)
                    new_rows.append(out_row)
        except csv.Error as exc:
            print(f"Некоректний CSV у {path}: {exc}")

    if new_rows:
        file_created = write_csv(verified_file, fieldnames, new_rows, append=True)
        action = "Створено" if file_created else "Оновлено"
        print(f"{action} файл {verified_file}")
        print(f"Додано {len(new_rows)} нових рядків.")
    else:
        print(f"Нових записів не додано до {verified_file}.")

    print(f"Опрацьовано {len(other_files)} файлів.")
    print(f"Знайдено {match_count} збігів по MAC.")
    print(f"Пропущено {dup_count} рядків через дублювання.")
