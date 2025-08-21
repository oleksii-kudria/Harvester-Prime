import csv

from scripts import process as sp
from app.processors.normalize import normalize_dhcp_records


def test_ignore_mac(tmp_path, monkeypatch):
    base_dir = tmp_path
    (base_dir / "configs").mkdir()
    (base_dir / "data/raw/dhcp").mkdir(parents=True)

    # configuration with MAC to ignore
    (base_dir / "configs/local.yml").write_text(
        "ignore:\n  mac:\n    test: 'AA:BB:CC:DD:EE:FF'\n",
        encoding="utf-8",
    )

    # raw DHCP log with two entries
    (base_dir / "data/raw/dhcp/sample.csv").write_text(
        "logSourceIdentifier,sourcMACAddress,payloadAsUTF,deviceTime\n"
        "src1,AA:BB:CC:DD:EE:FF,dhcp info assigned 192.168.1.2 for AA:BB:CC:DD:EE:FF,1\n"
        "src1,11:22:33:44:55:66,dhcp info assigned 192.168.1.3 for 11:22:33:44:55:66,2\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sp, "BASE_DIR", base_dir)

    records = sp.load_dhcp_logs(base_dir / "data/raw/dhcp")
    ignore_macs = sp._load_ignore_macs()
    records = [
        r for r in records
        if sp._normalize_mac(r.get("sourcMACAddress", "")) not in ignore_macs
    ]
    normalized = normalize_dhcp_records(records)
    dhcp_file = base_dir / "data/interim/dhcp.csv"
    sp.write_dhcp_interim(dhcp_file, normalized)

    with open(dhcp_file, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert [row["mac"] for row in rows] == ["11:22:33:44:55:66"]
