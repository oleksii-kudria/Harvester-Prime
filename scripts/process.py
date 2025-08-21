"""CLI wrappers for processing DHCP and inventory data."""
# ruff: noqa: E402
from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from app.collectors.files import (
    list_csv_files as _list_csv_files,
    load_dhcp_logs as _load_dhcp_logs,
    write_dhcp_interim as _write_dhcp_interim,
)
from app.config.loader import load_base_config as _load_base_config, ignored_macs as _ignored_macs
from app.config.schemas import read_csv_mapped
from app.processors.cleanup import clean_interim as _clean_interim
from app.processors.interim import run_arm_interim, run_mkp_interim, run_ubiq_interim
from app.processors.normalize import normalize_dhcp_records
from app.processors.verified import append_other_to_verified
from app.utils.mac import normalize as _normalize_mac
from app.utils.notes import normalize_note


def load_config() -> dict:
    """Load base configuration values."""

    return _load_base_config(str(BASE_DIR / "configs/base.yaml"))


def _load_ignore_macs() -> set[str]:
    """Return set of MAC addresses to ignore from local configuration."""

    return _ignored_macs(str(BASE_DIR / "configs/local.yml"))


def clean_interim(directory: Path | None = None) -> None:
    """Delete interim CSV files except examples."""

    pattern = str((directory or BASE_DIR / "data/interim").joinpath("*.csv"))
    removed = _clean_interim(pattern)
    for path in removed:
        print(f"[INFO] Видалено: {Path(path).name}")


# Re-export commonly used helpers for backward compatibility
list_csv_files = _list_csv_files
load_dhcp_logs = _load_dhcp_logs
write_dhcp_interim = _write_dhcp_interim
read_csv_mapped = read_csv_mapped
run_ubiq_interim = run_ubiq_interim
run_arm_interim = run_arm_interim
run_mkp_interim = run_mkp_interim
append_other_to_verified = append_other_to_verified
normalize_dhcp_records = normalize_dhcp_records
_normalize_mac = _normalize_mac
normalize_note = normalize_note


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        nargs="?",
        choices=["clean"],
        help="action to perform",
    )
    args = parser.parse_args(argv)

    if args.command == "clean":
        clean_interim()
        return

    config = load_config()
    paths = config.get("paths", {})
    raw_dir = BASE_DIR / paths.get("raw_dhcp", "data/raw/dhcp")
    interim_file = BASE_DIR / paths.get("interim_dhcp", "data/interim/dhcp.csv")

    if not list_csv_files(raw_dir):
        print(f"Відсутні файли DHCP у {raw_dir}. Обробку даних не запущено.")
        return

    records = load_dhcp_logs(raw_dir)
    ignore_macs = _load_ignore_macs()
    records = [
        r for r in records if _normalize_mac(r.get("sourcMACAddress", "")) not in ignore_macs
    ]
    normalized = normalize_dhcp_records(records)
    write_dhcp_interim(interim_file, normalized)


if __name__ == "__main__":
    main()
