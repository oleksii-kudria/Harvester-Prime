from __future__ import annotations

import csv
import sys
import types
from pathlib import Path


def read_rows(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_note_mapping_appended(tmp_path, capsys, monkeypatch):
    base_dir = tmp_path
    arm_dir = base_dir / "data/raw/arm"
    dhcp_file = base_dir / "data/interim/dhcp.csv"
    verified_file = base_dir / "data/interim/verified.csv"
    arm_dir.mkdir(parents=True)
    dhcp_file.parent.mkdir(parents=True)
    verified_file.parent.mkdir(parents=True, exist_ok=True)

    (arm_dir / "arm.csv").write_text(
        "Static MAC,Hostname,Власник,Тип ПК,Random MAC,Власність\n"
        "AA-AA-AA-AA-AA-01,pc1,owner1,офіс,,\n"
        "AA-AA-AA-AA-AA-02,pc2,owner2, х Р О М ,,\n"
        "AA-AA-AA-AA-AA-03,pc3,owner3,ігровий,,\n",
        encoding="utf-8",
    )

    dhcp_file.write_text(
        "source,ip,mac,firstDate,lastDate\n"
        "s1,1.1.1.1,AA:AA:AA:AA:AA:01,1,2\n"
        "s1,1.1.1.2,AA:AA:AA:AA:AA:02,1,2\n"
        "s1,1.1.1.3,AA:AA:AA:AA:AA:03,1,2\n",
        encoding="utf-8",
    )

    dummy_yaml = types.ModuleType("yaml")
    dummy_yaml.safe_load = lambda stream: {
        "arm": {
            "mac": "Static MAC",
            "hostname": "Hostname",
            "owner": "Власник",
            "pc_type": "Тип ПК",
            "randmac": "Random MAC",
            "ownership": "Власність",
        },
        "dhcp": {
            "mac": "mac",
            "ip": "ip",
            "source": "source",
            "firstDate": "firstDate",
            "lastDate": "lastDate",
        },
    }
    sys.modules["yaml"] = dummy_yaml
    sys.modules.pop("scripts.process", None)
    import scripts.process as process
    monkeypatch.setattr(process, "BASE_DIR", base_dir)
    process.SCHEMAS = dummy_yaml.safe_load(None)
    process.NOTE_MAPPING = {
        "офіс": "Microsoft Office",
        "хром": "Google Chrome",
    }

    process.run_arm_interim(arm_dir, dhcp_file, verified_file)
    rows = read_rows(verified_file)
    assert rows[0]["note"] == "Надано на перевірку. Microsoft Office"
    assert rows[1]["note"] == "Надано на перевірку. Google Chrome"
    assert rows[2]["note"] == "Надано на перевірку."

    captured = capsys.readouterr()
    assert "ігровий" in captured.out
