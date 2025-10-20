from __future__ import annotations

import csv
import importlib
from pathlib import Path


def test_generate_report1_includes_pending(tmp_path, monkeypatch):
    base_dir = tmp_path

    # Prepare configuration
    (base_dir / "configs").mkdir()
    (base_dir / "data" / "interim").mkdir(parents=True)
    (base_dir / "configs" / "base.yaml").write_text(
        """devices:
  router: "Маршрутизатор"
  arm: "АРМ"
""",
        encoding="utf-8",
    )

    # Verified device row
    (base_dir / "data" / "interim" / "verified.csv").write_text(
        "source,type,name,ip,mac,randmac,note,personal\n"
        "VSrc,router,RName,1.1.1.1,aa,,Extra,false\n",
        encoding="utf-8",
    )

    # Pending device row
    (base_dir / "data" / "interim" / "pending.csv").write_text(
        "source,name,ip,mac,randmac,type,firstDate,lastDate\n"
        "PSrc,PName,2.2.2.2,bb,,arm,2024-01-02 03:04,2024-02-03 04:05\n",
        encoding="utf-8",
    )

    gr = importlib.import_module("scripts.generate_report1")
    monkeypatch.setattr(gr, "BASE_DIR", base_dir)
    gr.main()

    report_path = base_dir / "data" / "result" / "report1.csv"
    with open(report_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 2
    pending = rows[1]
    assert pending["verified"] == "false"
    assert pending["type"] == "arm"
    assert pending["name"] == "АРМ\nPName"
    assert pending["ipmac"] == "2.2.2.2\nbb"
    assert (
        pending["note"]
        == "Не надано для перевірки.\nПерше підключення – 02.01.2024 03:04, останнє підключення – 03.02.2024 04:05."
    )


def test_generate_report1_handles_epoch_times(tmp_path, monkeypatch):
    base_dir = tmp_path

    (base_dir / "configs").mkdir()
    (base_dir / "data" / "interim").mkdir(parents=True)
    (base_dir / "configs" / "base.yaml").write_text(
        """devices:
  router: \"Маршрутизатор\"
  arm: \"АРМ\"
""",
        encoding="utf-8",
    )

    (base_dir / "data" / "interim" / "verified.csv").write_text(
        "source,type,name,ip,mac,randmac,note,personal\n"
        "VSrc,router,RName,1.1.1.1,aa,,Extra,false\n",
        encoding="utf-8",
    )

    first_epoch = "1704164640000"  # 2024-01-02 03:04
    last_epoch = "1706933100000"   # 2024-02-03 04:05
    (base_dir / "data" / "interim" / "pending.csv").write_text(
        "source,name,ip,mac,randmac,type,firstDate,lastDate\n"
        f"PSrc,PName,2.2.2.2,bb,,arm,{first_epoch},{last_epoch}\n",
        encoding="utf-8",
    )

    gr = importlib.import_module("scripts.generate_report1")
    monkeypatch.setattr(gr, "BASE_DIR", base_dir)
    gr.main()

    report_path = base_dir / "data" / "result" / "report1.csv"
    with open(report_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 2
    pending = rows[1]
    assert pending["note"] == (
        "Не надано для перевірки.\n"
        "Перше підключення – 02.01.2024 03:04, останнє підключення – 03.02.2024 04:05."
    )


def test_generate_report1_handles_last_date_only(tmp_path, monkeypatch):
    base_dir = tmp_path

    (base_dir / "configs").mkdir()
    (base_dir / "data" / "interim").mkdir(parents=True)
    (base_dir / "configs" / "base.yaml").write_text(
        """devices:
  router: \"Маршрутизатор\"
  arm: \"АРМ\"
""",
        encoding="utf-8",
    )

    (base_dir / "data" / "interim" / "verified.csv").write_text(
        "source,type,name,ip,mac,randmac,note,personal\n"
        "VSrc,router,RName,1.1.1.1,aa,,Extra,false\n",
        encoding="utf-8",
    )

    (base_dir / "data" / "interim" / "pending.csv").write_text(
        "source,name,ip,mac,randmac,type,firstDate,lastDate\n"
        "PSrc,PName,2.2.2.2,bb,,arm,,2024-02-03 04:05\n",
        encoding="utf-8",
    )

    gr = importlib.import_module("scripts.generate_report1")
    monkeypatch.setattr(gr, "BASE_DIR", base_dir)
    gr.main()

    report_path = base_dir / "data" / "result" / "report1.csv"
    with open(report_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 2
    pending = rows[1]
    assert (
        pending["note"]
        == "Не надано для перевірки.\nОстаннє підключення – 03.02.2024 04:05."
    )


def test_generate_report1_includes_randomized_note(tmp_path, monkeypatch):
    base_dir = tmp_path

    (base_dir / "configs").mkdir()
    (base_dir / "data" / "interim").mkdir(parents=True)
    (base_dir / "configs" / "base.yaml").write_text(
        """devices:
  router: "Маршрутизатор"
  arm: "АРМ"
""",
        encoding="utf-8",
    )

    (base_dir / "data" / "interim" / "verified.csv").write_text(
        "source,type,name,ip,mac,randmac,note,personal\n"
        "VSrc,router,RName,1.1.1.1,AA:BB:CC:DD:EE:FF,,,\n",
        encoding="utf-8",
    )

    (base_dir / "data" / "interim" / "pending.csv").write_text(
        "source,name,ip,mac,randmac,type,firstDate,lastDate\n"
        "PSrc,PName,2.2.2.2,11:22:33:44:55:66,,arm,2024-01-02 03:04,2024-02-03 04:05\n",
        encoding="utf-8",
    )

    (base_dir / "data" / "interim" / "dhcp.csv").write_text(
        "source,ip,mac,name,firstDate,lastDate,count,randomized\n"
        "s1,1.1.1.1,AA:BB:CC:DD:EE:FF,,0,0,1,true\n"
        "s2,2.2.2.2,11:22:33:44:55:66,,0,0,1,true\n",
        encoding="utf-8",
    )

    gr = importlib.import_module("scripts.generate_report1")
    monkeypatch.setattr(gr, "BASE_DIR", base_dir)
    gr.main()

    report_path = base_dir / "data" / "result" / "report1.csv"
    with open(report_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 2
    verified = rows[0]
    pending = rows[1]

    assert (
        verified["note"]
        == "Надано на перевірку.\nНа пристрої увімкнена генерація випадкової MAC-адреси."
    )
    assert (
        pending["note"]
        == "Не надано для перевірки.\n"
        "На пристрої увімкнена генерація випадкової MAC-адреси.\n"
        "Перше підключення – 02.01.2024 03:04, останнє підключення – 03.02.2024 04:05."
    )

