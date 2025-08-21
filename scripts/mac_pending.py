"""Check pending MACs against raw MKP CSV files.

This script reads ``data/interim/pending.csv`` and scans all CSV files in
``data/raw/mkp`` for partial MAC address matches (at least four consecutive
blocks). For each match, the corresponding rows from both sources are appended
to ``data/interim/mac-pending.csv``.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


def _mac_blocks(mac: str) -> list[str]:
    """Return colon-separated MAC address blocks in upper case."""
    return [block.upper() for block in mac.split(":") if block]


def _max_consecutive_blocks(mac1: str, mac2: str) -> int:
    """Return length of the longest common block sequence between two MACs."""
    blocks1 = _mac_blocks(mac1)
    blocks2 = _mac_blocks(mac2)
    max_match = 0
    for i in range(len(blocks1)):
        for j in range(len(blocks2)):
            k = 0
            while (
                i + k < len(blocks1)
                and j + k < len(blocks2)
                and blocks1[i + k] == blocks2[j + k]
            ):
                k += 1
            if k > max_match:
                max_match = k
    return max_match


def find_partial_mac_matches(
    pending_path: Path,
    raw_dir: Path,
    output_path: Path,
    *,
    min_blocks: int = 4,
) -> int:
    """Append matching rows to *output_path* and return number of matches.

    Parameters
    ----------
    pending_path:
        Path to ``pending.csv`` containing a ``mac`` column.
    raw_dir:
        Directory containing raw ``mkp`` CSV files.
    output_path:
        File where matches should be appended. Created if missing.
    min_blocks:
        Minimum number of consecutive matching blocks required (default 4).
    """

    if not pending_path.exists():
        return 0

    pending_df = pd.read_csv(pending_path, dtype=str).fillna("")
    pending_rows = pending_df.to_dict("records")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source", "file", "mac", "row"]
    file_exists = output_path.exists()
    written = 0

    with open(output_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for raw_file in sorted(raw_dir.glob("*.csv")):
            df = pd.read_csv(raw_file, dtype=str).fillna("")
            for _, row in df.iterrows():
                for col in ("Статичний MAC", "Динамічний MAC"):
                    mac_raw = row.get(col, "")
                    if not mac_raw:
                        continue
                    for pending_row in pending_rows:
                        mac_pending = pending_row.get("mac", "")
                        if mac_pending and _max_consecutive_blocks(mac_pending, mac_raw) >= min_blocks:
                            writer.writerow(
                                {
                                    "source": "pending",
                                    "file": str(pending_path),
                                    "mac": mac_pending,
                                    "row": pending_row,
                                }
                            )
                            writer.writerow(
                                {
                                    "source": "raw",
                                    "file": str(raw_file),
                                    "mac": mac_raw,
                                    "row": row.to_dict(),
                                }
                            )
                            written += 1
    return written


def main() -> None:
    base = Path(__file__).resolve().parents[1]
    pending_path = base / "data" / "interim" / "pending.csv"
    raw_dir = base / "data" / "raw" / "mkp"
    output_path = base / "data" / "interim" / "mac-pending.csv"
    find_partial_mac_matches(pending_path, raw_dir, output_path)


if __name__ == "__main__":
    main()
