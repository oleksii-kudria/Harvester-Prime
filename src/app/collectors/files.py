"""Utilities for working with CSV files."""
from __future__ import annotations

from pathlib import Path
import csv
from typing import Iterable, Dict, List, Set, Tuple

from app.io.csvio import read_csv

# Columns we are interested in within DHCP log files
DHCP_COLUMNS = [
    "logSourceIdentifier",
    "sourcMACAddress",
    "payloadAsUTF",
    "deviceTime",
]


def _is_valid_csv(path: Path) -> bool:
    """Return True if *path* points to a CSV file we should process."""
    return path.suffix == ".csv" and not path.name.endswith(".example.csv")


def list_csv_files(directory: Path) -> List[Path]:
    """List all CSV files within *directory* that should be processed."""
    directory = Path(directory)
    return [p for p in directory.glob("*.csv") if _is_valid_csv(p)]


def load_dhcp_logs(directory: Path) -> List[Dict[str, str]]:
    """Load and combine DHCP log entries from all CSV files in *directory*."""
    logs: List[Dict[str, str]] = []
    for file_path in list_csv_files(directory):
        logs.extend(read_csv(file_path))
    return logs


def write_dhcp_interim(path: Path, rows: Iterable[Dict[str, str]]) -> None:
    """Write normalized DHCP rows to *path* in CSV format.

    Existing records in the destination file are preserved and used to
    filter out duplicates from *rows*. A row is considered duplicate if
    all of its fields match an already stored row.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source", "ip", "mac", "name", "firstDate", "lastDate"]

    # Load existing records to avoid writing duplicates
    existing: Set[Tuple[str, ...]] = set()
    file_created = not path.exists()
    if not file_created:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                existing.add(
                    tuple(
                        row.get("name", row.get("hostname", ""))
                        if f == "name"
                        else row.get(f, "")
                        for f in fieldnames
                    )
                )
        mode = "a"
    else:
        mode = "w"

    new_count = 0
    dup_count = 0
    with open(path, mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        for row in rows:
            # Accept both ``name`` and legacy ``hostname`` keys
            normalized = {
                "source": row.get("source", ""),
                "ip": row.get("ip", ""),
                "mac": row.get("mac", ""),
                "name": row.get("name", row.get("hostname", "")),
                "firstDate": row.get("firstDate", ""),
                "lastDate": row.get("lastDate", ""),
            }
            record = tuple(normalized.get(f, "") for f in fieldnames)
            if record in existing:
                dup_count += 1
                continue
            writer.writerow(normalized)
            existing.add(record)
            new_count += 1

    if file_created:
        print(f"Створено файл {path}")
    else:
        print(f"Оновлено файл {path}")
    print(
        f"Додано {new_count} нових записів. "
        f"{dup_count} записів вже існували та не були додані."
    )
