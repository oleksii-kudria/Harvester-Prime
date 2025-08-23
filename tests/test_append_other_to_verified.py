from pathlib import Path
import csv
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.processors.verified import append_other_to_verified


def read_rows(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_append_and_idempotent(tmp_path: Path) -> None:
    other_dir = tmp_path / "data/raw/other"
    dhcp_file = tmp_path / "data/interim/dhcp.csv"
    verified_file = tmp_path / "data/interim/verified.csv"
    other_dir.mkdir(parents=True)
    dhcp_file.parent.mkdir(parents=True)
    verified_file.parent.mkdir(parents=True, exist_ok=True)

    # other csv with MAC containing spaces to test normalization
    (other_dir / "devices.csv").write_text(
        "type,name,ip,mac,note\nrouter,dev1,,aa bb cc dd ee ff,\n",
        encoding="utf-8",
    )

    dhcp_file.write_text(
        "source,ip,mac,firstDate,lastDate\n"
        "s1,10.0.0.1,AA:BB:CC:DD:EE:FF,1,2\n",
        encoding="utf-8",
    )

    append_other_to_verified(other_dir, dhcp_file, verified_file)
    rows = read_rows(verified_file)
    assert len(rows) == 1
    assert rows[0]["mac"] == "AA:BB:CC:DD:EE:FF"
    assert rows[0]["type"] == "router"
    assert rows[0]["source"] == "s1"
    assert rows[0]["personal"] == "false"

    # Second run should not duplicate
    append_other_to_verified(other_dir, dhcp_file, verified_file)
    rows = read_rows(verified_file)
    assert len(rows) == 1


def test_missing_inputs(tmp_path: Path) -> None:
    other_dir = tmp_path / "data/raw/other"
    dhcp_file = tmp_path / "data/interim/dhcp.csv"
    verified_file = tmp_path / "data/interim/verified.csv"

    # Do not create required files/directories
    append_other_to_verified(other_dir, dhcp_file, verified_file)
    assert not verified_file.exists()
