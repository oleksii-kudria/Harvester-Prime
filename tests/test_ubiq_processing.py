import csv
from pathlib import Path

from scripts.process import run_ubiq_interim


def read_rows(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_run_ubiq_interim(tmp_path):
    ubiq_dir = tmp_path / "data/raw/ubiq"
    ubiq_dir.mkdir(parents=True)
    sample = (
        "source,name,mac,ip,date\n"
        "\"192.168.55.1\",\"52:a0:16:86:e3:22\",\"52:a0:16:86:e3:22\",\"-\",\"Aug 07 2025\u00A03:01 PM\"\n"
        "\"192.168.55.1\",\"A36-phone\u00A0ca:49\",\"b1:67:2d:f4:ca:49\",\"192.168.5.175\",\"Aug 18 2025\u00A07:44 AM\"\n"
    )
    (ubiq_dir / "sample.csv").write_text(sample, encoding="utf-8")

    dhcp_file = tmp_path / "data/interim/dhcp.csv"
    run_ubiq_interim(ubiq_dir, dhcp_file)

    rows = read_rows(dhcp_file)
    assert rows == [
        {
            "source": "192.168.55.1",
            "ip": "",
            "mac": "52:A0:16:86:E3:22",
            "name": "unknown",
            "firstDate": "",
            "lastDate": "",
        },
        {
            "source": "192.168.55.1",
            "ip": "192.168.5.175",
            "mac": "B1:67:2D:F4:CA:49",
            "name": "A36-phone",
            "firstDate": "",
            "lastDate": "1755492240",
        },
    ]
