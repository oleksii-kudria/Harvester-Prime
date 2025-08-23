from pathlib import Path
import csv
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.process import run_arm_interim, run_mkp_interim


def read_rows(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_rarm_and_idempotent(tmp_path: Path) -> None:
    arm_dir = tmp_path / "data/raw/arm"
    dhcp_file = tmp_path / "data/interim/dhcp.csv"
    verified_file = tmp_path / "data/interim/verified.csv"
    arm_dir.mkdir(parents=True)
    dhcp_file.parent.mkdir(parents=True)
    verified_file.parent.mkdir(parents=True, exist_ok=True)

    (arm_dir / "arm.csv").write_text(
        "Static MAC,Hostname,Власник,Тип ПК,Random MAC,Власність\n"
        "AA-BB-CC-DD-EE-FF,host1,,pc,b1-67-2d-f4-ca-49,Особистий\n",
        encoding="utf-8",
    )

    dhcp_file.write_text(
        "source,ip,mac,firstDate,lastDate\n"
        "s1,10.0.0.1,B1:67:2D:F4:CA:49,1,2\n",
        encoding="utf-8",
    )

    run_arm_interim(arm_dir, dhcp_file, verified_file)
    rows = read_rows(verified_file)
    assert len(rows) == 1
    assert rows[0]["type"] == "rarm"
    assert rows[0]["mac"] == "B1:67:2D:F4:CA:49"
    assert rows[0]["randmac"] == "AA:BB:CC:DD:EE:FF"
    assert rows[0]["personal"] == "true"

    # Idempotent on second run
    run_arm_interim(arm_dir, dhcp_file, verified_file)
    rows2 = read_rows(verified_file)
    assert rows2 == rows


def test_rmkp_and_idempotent(tmp_path: Path) -> None:
    mkp_dir = tmp_path / "data/raw/mkp"
    dhcp_file = tmp_path / "data/interim/dhcp.csv"
    verified_file = tmp_path / "data/interim/verified.csv"
    mkp_dir.mkdir(parents=True)
    dhcp_file.parent.mkdir(parents=True)
    verified_file.parent.mkdir(parents=True, exist_ok=True)

    (mkp_dir / "mkp.csv").write_text(
        "Статичний MAC,Модель,Відповідальний,Тип МКП,Динамічний MAC,Категорія МКП\n"
        "AA-BB-CC-DD-EE-01,model1,owner1,,de.e4.16.ac.71.fe,особистий\n",
        encoding="utf-8",
    )

    dhcp_file.write_text(
        "source,ip,mac,firstDate,lastDate\n"
        "s1,10.0.0.2,DE:E4:16:AC:71:FE,3,4\n",
        encoding="utf-8",
    )

    run_mkp_interim(mkp_dir, dhcp_file, verified_file)
    rows = read_rows(verified_file)
    assert len(rows) == 1
    assert rows[0]["type"] == "rmkp"
    assert rows[0]["mac"] == "DE:E4:16:AC:71:FE"
    assert rows[0]["randmac"] == "AA:BB:CC:DD:EE:01"
    assert rows[0]["personal"] == "true"

    run_mkp_interim(mkp_dir, dhcp_file, verified_file)
    rows2 = read_rows(verified_file)
    assert rows2 == rows

