import csv
from pathlib import Path

from scripts.mac_pending import find_partial_mac_matches


def test_find_partial_mac_matches(tmp_path: Path) -> None:
    pending_dir = tmp_path / "data" / "interim"
    raw_dir = tmp_path / "data" / "raw" / "mkp"
    pending_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)

    pending_file = pending_dir / "pending.csv"
    pending_file.write_text("mac\nC2:3A:4B:5C:6D:7E\n", encoding="utf-8")

    raw_file = raw_dir / "sample.csv"
    raw_file.write_text(
        "Статичний MAC,Динамічний MAC\n" "2C:3A:4B:5C:6D:7E,AA:BB:CC:DD:EE:FF\n",
        encoding="utf-8",
    )

    output_file = pending_dir / "mac-pending.csv"
    count = find_partial_mac_matches(pending_file, raw_dir, output_file)
    assert count == 1

    with open(output_file, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[0]["source"] == "pending"
    assert rows[0]["mac"] == "C2:3A:4B:5C:6D:7E"
    assert rows[1]["source"] == "raw"
    assert rows[1]["mac"] == "2C:3A:4B:5C:6D:7E"

    # Calling again should append to the existing file
    count = find_partial_mac_matches(pending_file, raw_dir, output_file)
    assert count == 1
    with open(output_file, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 4
