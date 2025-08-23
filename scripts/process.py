"""Script to process raw DHCP log files into a normalized CSV.

This script reads configuration from ``configs/base.yaml`` to determine the
locations of the raw DHCP logs and the destination for the normalized interim
CSV file. The configuration allows these paths to be easily customised without
modifying the code.
"""
from __future__ import annotations

from pathlib import Path
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import re

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore
try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

# Ensure the src directory is on the Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from app.collectors.files import (
    load_dhcp_logs,
    write_dhcp_interim,
    list_csv_files,
    read_csv,
    write_csv,
)
from app.processors.normalize import normalize_dhcp_records
from app.processors.verified import append_other_to_verified


def load_schemas() -> dict:
    """Load column mappings from ``configs/schemas.yml``.

    The resulting dictionary contains mappings grouped by data source
    (``arm``, ``mkp``, ``dhcp`` ...). Each group maps canonical column names
    used within the code to the actual names present in the CSV files.
    """

    schema_path = BASE_DIR / "configs" / "schemas.yml"
    if yaml is None:
        return {}
    with open(schema_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


SCHEMAS = load_schemas()


def rename_hostname_column(path: Path) -> None:
    """Rename ``hostname`` column to ``name`` in *path* if present."""

    path = Path(path)
    if pd is None or not path.exists():
        return
    df = pd.read_csv(path, dtype=str)
    if "hostname" in df.columns and "name" not in df.columns:
        df = df.rename(columns={"hostname": "name"})
        df.to_csv(path, index=False)


def read_csv_mapped(path: Path, schema_key: str, columns: list[str]) -> list[dict[str, str]]:
    """Read *columns* from *path* using a schema definition.

    Parameters
    ----------
    path:
        CSV file to read.
    schema_key:
        Key of the schema section in ``configs/schemas.yml``.
    columns:
        Canonical column names to read.

    Returns
    -------
    list[dict[str, str]]
        Rows with keys renamed to canonical column names.
    """

    if schema_key in {"dhcp", "pending"}:
        rename_hostname_column(path)
    mapping = SCHEMAS.get(schema_key, {})
    actual_columns = [mapping.get(col, col) for col in columns]
    rows = read_csv(path, columns=actual_columns)
    remapped = []
    for row in rows:
        remapped.append({col: row.get(mapping.get(col, col), "") for col in columns})
    return remapped


def _format_timestamp(value: str) -> str:
    """Return *value* converted to ``DD.MM.YYYY HH:MM`` format.

    ``value`` is expected to be a Unix timestamp in seconds or milliseconds.
    If it cannot be parsed, an empty string is returned.
    """

    try:
        ts = int(value)
    except ValueError:
        return ""
    if ts > 1_000_000_000_000:  # milliseconds
        ts /= 1000
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def load_config() -> dict:
    """Load configuration values from ``configs/base.yaml``."""
    config_path = BASE_DIR / "configs" / "base.yaml"
    if yaml is None:
        return {}
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _load_note_mapping() -> dict[str, str]:
    """Load note replacements from ``configs/local.yml`` if present.

    The config may specify an empty ``target`` which indicates that matching
    ``note`` values should be replaced with an empty string.
    """

    config_path = BASE_DIR / "configs" / "local.yml"
    if yaml is None:
        return {}
    try:
        with open(config_path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}

    mapping: dict[str, str] = {}
    for app in (config.get("apps") or {}).values():
        source = (app.get("source") or "").strip()
        target = app.get("target")
        if source and target is not None:
            mapping[source.lower()] = target
    return mapping


NOTE_MAPPING = _load_note_mapping()


def _load_ignore_macs() -> set[str]:
    """Load MAC addresses to ignore from ``configs/local.yml`` if present."""

    config_path = BASE_DIR / "configs" / "local.yml"
    if yaml is None:
        return set()
    try:
        with open(config_path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return set()

    macs = set()
    invalid: list[str] = []
    for value in ((config.get("ignore") or {}).get("mac") or {}).values():
        mac_norm = _normalize_mac(str(value))
        if MAC_RE.fullmatch(mac_norm):
            macs.add(mac_norm)
        else:
            invalid.append(str(value))

    if invalid:
        print(
            "Попередження: некоректні MAC-адреси у configs/local.yml: "
            + ", ".join(invalid)
        )
    if macs:
        print("Ігноруються MAC-адреси: " + ", ".join(sorted(macs)))
    return macs


def normalize_note(note: str) -> str:
    """Return note value replaced according to NOTE_MAPPING."""

    key = (note or "").strip().lower()
    return NOTE_MAPPING.get(key, note)


def run_validation(validation_dir: Path, dhcp_file: Path, report_file: Path) -> None:
    """Validate MAC addresses from *validation_dir* against *dhcp_file*.

    The resulting report is written to *report_file* with columns
    ``name``, ``ipmac`` and ``note``.
    """
    validation_dir = Path(validation_dir)
    dhcp_file = Path(dhcp_file)
    report_file = Path(report_file)

    # Load validation records (ip, mac) normalising MAC to uppercase
    validation_records = []
    if validation_dir.exists():
        for path in list_csv_files(validation_dir):
            for row in read_csv_mapped(path, "validation", ["ip", "mac"]):
                mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
                validation_records.append({"ip": row.get("ip", ""), "mac": mac})

    # Load DHCP records indexed by normalised MAC
    dhcp_records = {}
    if dhcp_file.exists():
        for row in read_csv_mapped(
            dhcp_file, "dhcp", ["mac", "name", "ip", "firstDate", "lastDate"]
        ):
            mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
            dhcp_records[mac] = row

    matched_macs = set()
    report_rows = []

    for record in validation_records:
        mac = record.get("mac", "")
        ip = record.get("ip", "")
        dhcp_row = dhcp_records.get(mac)
        if dhcp_row:
            report_rows.append(
                {
                    "name": dhcp_row.get("name", ""),
                    "ipmac": f"{dhcp_row.get('ip', '')}\n{mac}",
                    "note": "Надано на перевірку.",
                }
            )
            matched_macs.add(mac)
        else:
            report_rows.append(
                {
                    "name": "unknown",
                    "ipmac": f"{ip}\n{mac}",
                    "note": "Пристрій відсутній на локації.",
                }
            )

    for mac, dhcp_row in dhcp_records.items():
        if mac in matched_macs:
            continue
        first_seen = _format_timestamp(dhcp_row.get("firstDate", ""))
        last_seen = _format_timestamp(dhcp_row.get("lastDate", ""))
        note = "Не надано для перевірки."
        if first_seen or last_seen:
            note += f" Перше підключення – {first_seen}, останнє підключення – {last_seen}."
        report_rows.append(
            {
                "name": dhcp_row.get("name", ""),
                "ipmac": f"{dhcp_row.get('ip', '')}\n{mac}",
                "note": note,
            }
        )

    fieldnames = ["name", "ipmac", "note"]
    file_created = write_csv(report_file, fieldnames, report_rows)
    action = "Створено" if file_created else "Оновлено"
    print(f"{action} файл {report_file}")
    print(f"Додано {len(report_rows)} нових записів.")


IP_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}([-:][0-9A-Fa-f]{2}){5}$")


def _normalize_spaces(value: str) -> str:
    """Return *value* with NBSP replaced and consecutive spaces collapsed."""

    return " ".join((value or "").replace("\u00A0", " ").split())


def _normalize_mac(value: str) -> str:
    """Return MAC address in ``XX:XX:XX:XX:XX:XX`` format if possible."""

    raw = (value or "").strip()
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", raw)
    if len(cleaned) == 12:
        parts = [cleaned[i : i + 2] for i in range(0, 12, 2)]
        return ":".join(parts).upper()
    return raw.upper().replace("-", ":")


def _validate_ip(value: str) -> str:
    """Return *value* if it is a valid IPv4 address, otherwise an empty string."""

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
    """Normalise *name* applying special MAC-related rules."""

    name = _normalize_spaces(name)
    mac_norm = _normalize_mac(mac)
    mac_plain = re.sub(r"[^0-9A-Fa-f]", "", mac_norm).upper()
    name_plain = re.sub(r"[^0-9A-Fa-f]", "", name).upper()
    if name_plain == mac_plain:
        return "unknown"
    tail = mac_norm[-5:].lower()
    if name.lower().endswith(f" {tail}"):
        return name[: -len(tail) - 1]
    return name


def _parse_last_date(date_str: str, ip: str) -> str:
    """Return epoch timestamp for *date_str* if *ip* is valid."""

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
    """Process Ubiq CSV files and append results to *dhcp_file*.

    Parameters
    ----------
    ubiq_dir:
        Directory containing Ubiq CSV files.
    dhcp_file:
        Path to the interim DHCP file to append to.
    ignore_macs:
        Optional set of normalised MAC addresses that should be skipped.
    """

    ubiq_dir = Path(ubiq_dir)
    dhcp_file = Path(dhcp_file)
    files = list_csv_files(ubiq_dir)
    if not files:
        print(f"Відсутні файли Ubiq у {ubiq_dir}. Крок Ubiq пропущено.")
        return

    rows = []
    for path in files:
        for row in read_csv(path, columns=["source", "name", "mac", "ip", "date"]):
            mac = _normalize_mac(row.get("mac", ""))
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
    """Add ARM records matched with DHCP data to *verified_file*.

    Rows are written with columns ``type``, ``source``, ``name``, ``ip``,
    ``mac``, ``randmac``, ``owner``, ``note``, ``firstDate``, ``lastDate`` and
    ``personal``. Only records where the MAC address from ``arm_dir`` is present
    in ``dhcp_file`` are included. Existing entries in *verified_file* are
    preserved and duplicates are skipped.
    """

    arm_dir = Path(arm_dir)
    dhcp_file = Path(dhcp_file)
    verified_file = Path(verified_file)

    if not dhcp_file.exists():
        print(
            f"Відсутній файл DHCP {dhcp_file}. Крок перевірки ARM (interim) пропущено."
        )
        return

    # Load DHCP records indexed by normalised MAC
    dhcp_records = {}
    for row in read_csv_mapped(
        dhcp_file, "dhcp", ["mac", "source", "ip", "name", "firstDate", "lastDate"]
    ):
        mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
        dhcp_records[mac] = row

    # Load existing MACs from the verified file
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
            columns = ["mac", "hostname", "owner", "pc_type", "randmac", "ownership"]
            rows = read_csv_mapped(path, "arm", columns)
            print(f"DEBUG: Читання файлу {path}")
            print(f"DEBUG: Стовпці: {columns}")
            for row in rows:
                print(f"DEBUG: Ключі: {list(row.keys())}")
                print(f"DEBUG: Дані: {row}")
                mac_raw = (row.get("mac", "") or "").strip()
                if MAC_RE.fullmatch(mac_raw):
                    mac = mac_raw.upper().replace("-", ":")
                else:
                    mac = ""
                rand_raw = (row.get("randmac", "") or "").strip()
                rand_norm = _normalize_mac(rand_raw)
                if rand_raw and not MAC_RE.fullmatch(rand_norm):
                    invalid_rand += 1
                    rand_norm = ""
                is_personal = (row.get("ownership", "") or "").strip().lower() == "особистий"

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
                                "personal": "true" if is_personal else "false",
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
                                "personal": "true" if is_personal else "false",
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
        "personal",
    ]
    print(f"DEBUG: Запис до файлу {verified_file}")
    print(f"DEBUG: Стовпці: {fieldnames}")
    for row in rows_to_write:
        print(f"DEBUG: Дані: {row}")
    file_created = write_csv(verified_file, fieldnames, rows_to_write, append=True)
    action = "Створено" if file_created else "Оновлено"
    print(f"{action} файл {verified_file}")
    print(f"Додано {len(rows_to_write)} нових записів.")
    print(f"Опрацьовано {file_count} файлів.")
    print(f"Знайдено {rand_matches} збігів по Random MAC.")
    print(f"Пропущено {invalid_rand} рядків через невалідні Random MAC.")


def run_mkp_interim(mkp_dir: Path, dhcp_file: Path, verified_file: Path) -> None:
    """Add MKP records matched with DHCP data to *verified_file*.

    The behaviour mirrors :func:`run_arm_interim` but works with MKP inventory
    files and writes rows with ``type`` set to ``"mkp"``. The resulting rows
    also include the ``source`` column from DHCP data. An additional ``randmac``
    column is populated from the "Динамічний MAC" field when it contains a
    valid MAC address; otherwise the column is left empty. Each row also
    contains a ``personal`` flag derived from the ``Категорія МКП`` column.
    """

    mkp_dir = Path(mkp_dir)
    dhcp_file = Path(dhcp_file)
    verified_file = Path(verified_file)

    if not dhcp_file.exists():
        print(
            f"Відсутній файл DHCP {dhcp_file}. Крок перевірки МКП (interim) пропущено."
        )
        return

    # Load DHCP records indexed by normalised MAC
    dhcp_records = {}
    for row in read_csv_mapped(
        dhcp_file, "dhcp", ["mac", "source", "ip", "name", "firstDate", "lastDate"]
    ):
        mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
        dhcp_records[mac] = row

    # Load existing MACs from the verified file
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
                ["mac", "model", "owner", "mkp_type", "randmac", "category"],
            ):
                mac_raw = (row.get("mac", "") or "").strip()
                mac_norm = _normalize_mac(mac_raw)
                if mac_raw and not MAC_RE.fullmatch(mac_norm):
                    mac_norm = ""
                rand_raw = (row.get("randmac", "") or "").strip()
                rand_norm = _normalize_mac(rand_raw)
                if rand_raw and not MAC_RE.fullmatch(rand_norm):
                    invalid_rand += 1
                    rand_norm = ""
                is_personal = (row.get("category", "") or "").strip().lower() == "особистий"

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
                                "personal": "true" if is_personal else "false",
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
                                "personal": "true" if is_personal else "false",
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
        "personal",
    ]
    file_created = write_csv(verified_file, fieldnames, rows_to_write, append=True)
    action = "Створено" if file_created else "Оновлено"
    print(f"{action} файл {verified_file}")
    print(f"Додано {len(rows_to_write)} нових записів.")
    print(f"Опрацьовано {file_count} файлів.")
    print(f"Знайдено {rand_matches} збігів по Random MAC.")
    print(f"Пропущено {invalid_rand} рядків через невалідні Random MAC.")

def run_arm_check(arm_dir: Path, dhcp_file: Path, report_file: Path) -> None:
    """Generate ARM report from *arm_dir* against *dhcp_file*.

    The report is written to *report_file* with columns ``name``, ``ipmac``,
    ``owner`` and ``note``. Rows are appended only if they are not already
    present in the report.
    """

    arm_dir = Path(arm_dir)
    dhcp_file = Path(dhcp_file)
    report_file = Path(report_file)

    if not dhcp_file.exists():
        print(f"Відсутній файл DHCP {dhcp_file}. Крок перевірки ARM пропущено.")
        return

    # Load DHCP records indexed by normalized MAC
    dhcp_records = {}
    for row in read_csv_mapped(dhcp_file, "dhcp", ["mac", "ip"]):
        mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
        dhcp_records[mac] = row

    # Load existing MACs from the report to avoid duplicates
    existing_macs = set()
    if report_file.exists():
        for row in read_csv_mapped(report_file, "report", ["ipmac"]):
            ipmac = row.get("ipmac", "")
            if not ipmac:
                continue
            parts = ipmac.splitlines()
            if parts:
                existing_macs.add(parts[-1].strip().upper().replace("-", ":"))

    matched_rows = []
    unmatched_rows = []
    duplicates = 0

    if arm_dir.exists():
        for path in list_csv_files(arm_dir):
            for row in read_csv_mapped(
                path, "arm", ["mac", "hostname", "owner", "pc_type", "ip"]
            ):
                mac_raw = row.get("mac", "").strip()
                if not MAC_RE.fullmatch(mac_raw):
                    continue
                mac = mac_raw.upper().replace("-", ":")
                if mac in existing_macs:
                    duplicates += 1
                    continue
                hostname = row.get("hostname", "")
                owner = row.get("owner", "")
                type_pc = row.get("pc_type", "")
                dhcp_row = dhcp_records.get(mac)
                if dhcp_row:
                    matched_rows.append(
                        {
                            "name": f"АРМ\n{hostname}",
                            "ipmac": f"{dhcp_row.get('ip', '')}\n{mac}",
                            "owner": owner,
                            "note": type_pc,
                        }
                    )
                else:
                    ip = (row.get("IP", "") or "").strip()
                    ipmac = f"{ip}\n{mac}" if ip else f"-\n{mac}"
                    unmatched_rows.append(
                        {
                            "name": f"АРМ\n{hostname}",
                            "ipmac": ipmac,
                            "owner": owner,
                            "note": type_pc,
                        }
                    )
                existing_macs.add(mac)
    else:
        print(f"Відсутні файли для перевірки у {arm_dir}. Крок ARM пропущено.")

    report_rows = matched_rows + unmatched_rows

    if not report_rows:
        print(
            f"Нових записів не додано до {report_file}. "
            f"{duplicates} записів вже існували."
        )
        return

    fieldnames = ["name", "ipmac", "owner", "note"]
    file_created = write_csv(report_file, fieldnames, report_rows, append=True)
    action = "Створено" if file_created else "Оновлено"
    print(f"{action} файл {report_file}")
    print(
        f"Додано {len(report_rows)} нових записів. "
        f"{duplicates} записів вже існували та не були додані."
    )


def run_mkp_check(mkp_dir: Path, dhcp_file: Path, report_file: Path) -> None:
    """Generate MKP report from *mkp_dir* against *dhcp_file*.

    Rows are appended to *report_file* with columns ``name``, ``ipmac``,
    ``owner`` and ``note``. Existing entries are not duplicated.
    """

    mkp_dir = Path(mkp_dir)
    dhcp_file = Path(dhcp_file)
    report_file = Path(report_file)

    if not dhcp_file.exists():
        print(f"Відсутній файл DHCP {dhcp_file}. Крок перевірки МКП пропущено.")
        return

    # Load DHCP records indexed by normalised MAC
    dhcp_records = {}
    for row in read_csv_mapped(dhcp_file, "dhcp", ["mac", "ip"]):
        mac = (row.get("mac", "") or "").strip().upper().replace("-", ":")
        dhcp_records[mac] = row

    # Load existing MACs from the report to avoid duplicates
    existing_macs = set()
    if report_file.exists():
        for row in read_csv_mapped(report_file, "report", ["ipmac"]):
            ipmac = row.get("ipmac", "")
            if not ipmac:
                continue
            parts = ipmac.splitlines()
            if parts:
                existing_macs.add(parts[-1].strip().upper().replace("-", ":"))

    matched_rows = []
    unmatched_rows = []
    duplicates = 0

    if mkp_dir.exists():
        for path in list_csv_files(mkp_dir):
            for row in read_csv_mapped(
                path, "mkp", ["mac", "model", "owner", "mkp_type"]
            ):
                mac_raw = (row.get("mac", "") or "").strip()
                if not MAC_RE.fullmatch(mac_raw):
                    continue
                mac = mac_raw.upper().replace("-", ":")
                if mac in existing_macs:
                    duplicates += 1
                    continue
                model = row.get("model", "")
                owner = row.get("owner", "")
                mkp_type = row.get("mkp_type", "")
                dhcp_row = dhcp_records.get(mac)
                if dhcp_row:
                    matched_rows.append(
                        {
                            "name": f"МКП\n{model}",
                            "ipmac": f"{dhcp_row.get('ip', '')}\n{mac}",
                            "owner": owner,
                            "note": mkp_type,
                        }
                    )
                else:
                    unmatched_rows.append(
                        {
                            "name": f"МКП\n{model}",
                            "ipmac": mac,
                            "owner": owner,
                            "note": mkp_type,
                        }
                    )
                existing_macs.add(mac)
    else:
        print(f"Відсутні файли для перевірки у {mkp_dir}. Крок МКП пропущено.")

    report_rows = matched_rows + unmatched_rows

    if not report_rows:
        print(
            f"Нових записів не додано до {report_file}. "
            f"{duplicates} записів вже існували."
        )
        return

    fieldnames = ["name", "ipmac", "owner", "note"]
    file_created = write_csv(report_file, fieldnames, report_rows, append=True)
    action = "Створено" if file_created else "Оновлено"
    print(f"{action} файл {report_file}")
    print(
        f"Додано {len(report_rows)} нових записів. "
        f"{duplicates} записів вже існували та не були додані."
    )


def run_pending_check(
    dhcp_file: Path, verified_file: Path, pending_file: Path
) -> None:
    """Write DHCP records absent from ``verified_file`` to ``pending_file``."""

    dhcp_file = Path(dhcp_file)
    verified_file = Path(verified_file)
    pending_file = Path(pending_file)

    if not dhcp_file.exists() or not verified_file.exists():
        missing = []
        if not dhcp_file.exists():
            missing.append(str(dhcp_file))
        if not verified_file.exists():
            missing.append(str(verified_file))
        print(
            f"Відсутній файл або файли: {', '.join(missing)}. "
            "Крок перевірки пропущено."
        )
        return

    verified_macs = {
        (row.get("mac", "") or "").strip().upper()
        for row in read_csv_mapped(verified_file, "verified", ["mac"])
    }

    from app.classifiers.device_type import DeviceTypeClassifier

    classifier = DeviceTypeClassifier(BASE_DIR / "configs" / "device_type_rules.yml")
    fieldnames = ["type", "source", "ip", "mac", "name", "firstDate", "lastDate"]
    append = pending_file.exists()
    existing = set()
    if append:
        for row in read_csv_mapped(pending_file, "pending", fieldnames):
            existing.add(tuple(row.get(f, "") for f in fieldnames))

    dhcp_fields = fieldnames[1:]
    rows_to_write = []
    for row in read_csv_mapped(dhcp_file, "dhcp", dhcp_fields):
        mac = (row.get("mac", "") or "").strip().upper()
        if mac in verified_macs:
            continue
        row_type = classifier.classify(row.get("name", ""))
        record = (row_type,) + tuple(row.get(f, "") for f in dhcp_fields)
        if record in existing:
            continue
        row_to_write = {f: row.get(f, "") for f in dhcp_fields}
        row_to_write["type"] = row_type
        rows_to_write.append(row_to_write)
        existing.add(record)

    file_created = write_csv(pending_file, fieldnames, rows_to_write, append=append)
    action = "Створено" if file_created else "Оновлено"
    print(f"{action} файл {pending_file}")
    print(f"Додано {len(rows_to_write)} нових записів.")


def clean_interim(directory: Path | None = None) -> None:
    """Delete interim CSV files except examples.

    Files ending with ``.example.csv`` are preserved. Missing directories or
    files are ignored.
    """

    directory = Path(directory or BASE_DIR / "data/interim")
    for path in directory.glob("*.csv"):
        if path.name.endswith(".example.csv"):
            print(f"[INFO] Залишено: {path.name}")
            continue
        try:
            path.unlink()
            print(f"[INFO] Видалено: {path.name}")
        except FileNotFoundError:  # pragma: no cover - already deleted
            pass


def main(argv: list[str] | None = None) -> None:
    argv = list(argv or sys.argv[1:])
    if argv and argv[0] == "clean":
        clean_interim()
        argv = argv[1:]

    config = load_config()
    paths = config.get("paths", {})

    raw_dir = BASE_DIR / paths.get("raw_dhcp", "data/raw/dhcp")
    interim_file = BASE_DIR / paths.get("interim_dhcp", "data/interim/dhcp.csv")

    if not list_csv_files(raw_dir):
        print(f"Відсутні файли DHCP у {raw_dir}. Обробку даних не запущено.")
        return

    records = load_dhcp_logs(raw_dir)
    ignore_macs = _load_ignore_macs()
    before_count = len(records)
    records = [
        r
        for r in records
        if _normalize_mac(r.get("sourcMACAddress", "")) not in ignore_macs
    ]
    after_count = len(records)
    print(
        f"Зчитано {before_count} записів DHCP. Відфільтровано {before_count - after_count}. "
        f"Залишилось {after_count}."
    )
    normalized = normalize_dhcp_records(records)
    write_dhcp_interim(interim_file, normalized)

    ubiq_dir = BASE_DIR / paths.get("raw_ubiq", "data/raw/ubiq")
    run_ubiq_interim(ubiq_dir, interim_file, ignore_macs)

    validation_dir = BASE_DIR / paths.get("raw_validation", "data/raw/validation")
    if list_csv_files(validation_dir):
        report_file = BASE_DIR / paths.get(
            "validation_report", "data/result/report1.csv"
        )
        run_validation(validation_dir, interim_file, report_file)
    else:
        print(
            f"Відсутні файли для валідації у {validation_dir}. Крок перевірки пропущено."
        )

    arm_dir = BASE_DIR / paths.get("raw_arm", "data/raw/arm")
    mkp_dir = BASE_DIR / paths.get("raw_mkp", "data/raw/mkp")
    other_dir = BASE_DIR / paths.get("raw_other", "data/raw/other")
    verified_file = BASE_DIR / "data/interim/verified.csv"
    run_arm_interim(arm_dir, interim_file, verified_file)
    run_mkp_interim(mkp_dir, interim_file, verified_file)
    append_other_to_verified(other_dir, interim_file, verified_file)
    report_file2 = BASE_DIR / paths.get(
        "arm_mkp_report", "data/result/120report2.csv"
    )
    run_arm_check(arm_dir, interim_file, report_file2)
    run_mkp_check(mkp_dir, interim_file, report_file2)
    pending_file = BASE_DIR / "data/interim/pending.csv"
    run_pending_check(interim_file, verified_file, pending_file)


if __name__ == "__main__":
    main()
