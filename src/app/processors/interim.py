"""Processing helpers for interim CSV generation."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict
from zoneinfo import ZoneInfo

from app.collectors.files import list_csv_files, write_dhcp_interim
from app.io.csvio import write_csv
from app.config.schemas import read_csv_mapped
from app.utils.mac import normalize as normalize_mac, MAC_RE
from app.utils.notes import normalize_note

IP_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def _normalize_spaces(value: str) -> str:
    return " ".join((value or "").replace("\u00A0", " ").split())


def _validate_ip(value: str) -> str:
    value = _normalize_spaces(value)
    if not value or value == "-" or not IP_RE.fullmatch(value):
        return ""
    try:
        if any(int(octet) > 255 for octet in value.split(".")):
            return ""
    except ValueError:
        return ""
    return value


def _normalize_name(name: str, mac: str) -> str:
    name = _normalize_spaces(name)
    mac_norm = normalize_mac(mac)
    mac_plain = re.sub(r"[^0-9A-Fa-f]", "", mac_norm).upper()
    name_plain = re.sub(r"[^0-9A-Fa-f]", "", name).upper()
    if name_plain == mac_plain:
        return "unknown"
    tail = mac_norm[-5:].lower()
    if name.lower().endswith(f" {tail}"):
        return name[: -len(tail) - 1]
    return name


def _parse_last_date(date_str: str, ip: str) -> str:
    if not ip:
        return ""
    date_str = _normalize_spaces(date_str)
    try:
        dt = datetime.strptime(date_str, "%b %d %Y %I:%M %p").replace(
            tzinfo=ZoneInfo("Europe/Kyiv")
        )
    except ValueError:
        return ""
    return str(int(dt.timestamp()))


def run_ubiq_interim(
    ubiq_dir: Path, dhcp_file: Path, ignore_macs: set[str] | None = None
) -> None:
    ubiq_dir = Path(ubiq_dir)
    dhcp_file = Path(dhcp_file)
    files = list_csv_files(ubiq_dir)
    if not files:
        print(f"Відсутні файли Ubiq у {ubiq_dir}. Крок Ubiq пропущено.")
        return

    rows = []
    for path in files:
        for row in read_csv_mapped(path, "ubiq", ["source", "name", "mac", "ip", "date"]):
            mac = normalize_mac(row.get("mac", ""))
            if ignore_macs and mac in ignore_macs:
                continue
            ip = _validate_ip(row.get("ip", ""))
            rows.append(
                {
                    "source": _normalize_spaces(row.get("source", "")),
                    "ip": ip,
                    "mac": mac,
                    "name": _normalize_name(row.get("name", ""), mac),
                    "firstDate": "",
                    "lastDate": _parse_last_date(row.get("date", ""), ip),
                }
            )

    write_dhcp_interim(dhcp_file, rows)


def run_arm_interim(arm_dir: Path, dhcp_file: Path, verified_file: Path) -> None:
    arm_dir = Path(arm_dir)
    dhcp_file = Path(dhcp_file)
    verified_file = Path(verified_file)

    if not dhcp_file.exists():
        print(f"Відсутній файл DHCP {dhcp_file}. Крок перевірки ARM (interim) пропущено.")
        return

    dhcp_records: Dict[str, Dict[str, str]] = {}
    for row in read_csv_mapped(
        dhcp_file, "dhcp", ["mac", "source", "ip", "name", "firstDate", "lastDate"]
    ):
        mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
        dhcp_records[mac] = row

    existing_macs = set()
    if verified_file.exists():
        for row in read_csv_mapped(verified_file, "verified", ["mac"]):
            mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
            if mac:
                existing_macs.add(mac)

    rows_to_write = []
    file_count = 0
    rand_matches = 0
    invalid_rand = 0

    if arm_dir.exists():
        for path in list_csv_files(arm_dir):
            file_count += 1
            for row in read_csv_mapped(
                path, "arm", ["mac", "hostname", "owner", "pc_type", "randmac"]
            ):
                mac_raw = (row.get("mac", "") or "").strip()
                if MAC_RE.fullmatch(mac_raw):
                    mac = mac_raw.upper().replace("-", ":")
                else:
                    mac = ""
                rand_raw = (row.get("randmac", "") or "").strip()
                rand_norm = normalize_mac(rand_raw)
                if rand_raw and not MAC_RE.fullmatch(rand_norm):
                    invalid_rand += 1
                    rand_norm = ""

                if mac and mac not in existing_macs:
                    dhcp_row = dhcp_records.get(mac)
                    if dhcp_row:
                        rows_to_write.append(
                            {
                                "type": "arm",
                                "source": dhcp_row.get("source", ""),
                                "name": row.get("hostname", ""),
                                "ip": dhcp_row.get("ip", ""),
                                "mac": mac,
                                "randmac": "",
                                "owner": row.get("owner", ""),
                                "note": normalize_note(row.get("pc_type", "")),
                                "firstDate": dhcp_row.get("firstDate", ""),
                                "lastDate": dhcp_row.get("lastDate", ""),
                            }
                        )
                        existing_macs.add(mac)

                if rand_norm and rand_norm not in existing_macs:
                    dhcp_row = dhcp_records.get(rand_norm)
                    if dhcp_row:
                        rows_to_write.append(
                            {
                                "type": "rarm",
                                "source": dhcp_row.get("source", ""),
                                "name": row.get("hostname", ""),
                                "ip": dhcp_row.get("ip", ""),
                                "mac": rand_norm,
                                "randmac": mac,
                                "owner": row.get("owner", ""),
                                "note": normalize_note(row.get("pc_type", "")),
                                "firstDate": dhcp_row.get("firstDate", ""),
                                "lastDate": dhcp_row.get("lastDate", ""),
                            }
                        )
                        existing_macs.add(rand_norm)
                        rand_matches += 1
    else:
        print(f"Відсутні файли для перевірки у {arm_dir}. Крок ARM interim пропущено.")

    if not rows_to_write:
        print(f"Нових записів не додано до {verified_file}.")
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
    write_csv(verified_file, fieldnames, rows_to_write, append=True)
    print(f"Опрацьовано {file_count} файлів.")
    print(f"Знайдено {rand_matches} збігів по Random MAC.")
    print(f"Пропущено {invalid_rand} рядків через невалідні Random MAC.")


def run_mkp_interim(mkp_dir: Path, dhcp_file: Path, verified_file: Path) -> None:
    mkp_dir = Path(mkp_dir)
    dhcp_file = Path(dhcp_file)
    verified_file = Path(verified_file)

    if not dhcp_file.exists():
        print(f"Відсутній файл DHCP {dhcp_file}. Крок перевірки МКП (interim) пропущено.")
        return

    dhcp_records: Dict[str, Dict[str, str]] = {}
    for row in read_csv_mapped(
        dhcp_file, "dhcp", ["mac", "source", "ip", "name", "firstDate", "lastDate"]
    ):
        mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
        dhcp_records[mac] = row

    existing_macs = set()
    if verified_file.exists():
        for row in read_csv_mapped(verified_file, "verified", ["mac"]):
            mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
            if mac:
                existing_macs.add(mac)

    rows_to_write = []
    file_count = 0
    rand_matches = 0
    invalid_rand = 0

    if mkp_dir.exists():
        for path in list_csv_files(mkp_dir):
            file_count += 1
            for row in read_csv_mapped(
                path,
                "mkp",
                ["mac", "model", "owner", "mkp_type", "randmac"],
            ):
                mac_raw = (row.get("mac", "") or "").strip()
                mac_norm = normalize_mac(mac_raw)
                if mac_raw and not MAC_RE.fullmatch(mac_norm):
                    mac_norm = ""
                rand_raw = (row.get("randmac", "") or "").strip()
                rand_norm = normalize_mac(rand_raw)
                if rand_raw and not MAC_RE.fullmatch(rand_norm):
                    invalid_rand += 1
                    rand_norm = ""

                if mac_norm and mac_norm not in existing_macs:
                    dhcp_row = dhcp_records.get(mac_norm)
                    if dhcp_row:
                        rows_to_write.append(
                            {
                                "type": "mkp",
                                "source": dhcp_row.get("source", ""),
                                "name": row.get("model", ""),
                                "ip": dhcp_row.get("ip", ""),
                                "mac": mac_norm,
                                "randmac": rand_norm,
                                "owner": row.get("owner", ""),
                                "note": normalize_note(row.get("mkp_type", "")),
                                "firstDate": dhcp_row.get("firstDate", ""),
                                "lastDate": dhcp_row.get("lastDate", ""),
                            }
                        )
                        existing_macs.add(mac_norm)

                if rand_norm and rand_norm not in existing_macs:
                    dhcp_row = dhcp_records.get(rand_norm)
                    if dhcp_row:
                        rows_to_write.append(
                            {
                                "type": "rmkp",
                                "source": dhcp_row.get("source", ""),
                                "name": row.get("model", ""),
                                "ip": dhcp_row.get("ip", ""),
                                "mac": rand_norm,
                                "randmac": mac_norm,
                                "owner": row.get("owner", ""),
                                "note": normalize_note(row.get("mkp_type", "")),
                                "firstDate": dhcp_row.get("firstDate", ""),
                                "lastDate": dhcp_row.get("lastDate", ""),
                            }
                        )
                        existing_macs.add(rand_norm)
                        rand_matches += 1
    else:
        print(f"Відсутні файли для перевірки у {mkp_dir}. Крок МКП interim пропущено.")

    if not rows_to_write:
        print(f"Нових записів не додано до {verified_file}.")
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
    write_csv(verified_file, fieldnames, rows_to_write, append=True)
    print(f"Опрацьовано {file_count} файлів.")
    print(f"Знайдено {rand_matches} збігів по Random MAC.")
    print(f"Пропущено {invalid_rand} рядків через невалідні Random MAC.")


__all__ = ["run_ubiq_interim", "run_arm_interim", "run_mkp_interim"]
