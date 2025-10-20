from __future__ import annotations

import csv
import importlib


def test_personal_suffix_in_note(tmp_path, monkeypatch):
    base_dir = tmp_path
    (base_dir / "configs").mkdir()
    (base_dir / "data" / "interim").mkdir(parents=True)
    (base_dir / "configs" / "base.yaml").write_text(
        """devices:
  arm: "АРМ"
  mkp: "МКП"
""",
        encoding="utf-8",
    )

    (base_dir / "data" / "interim" / "verified.csv").write_text(
        "source,type,name,ip,mac,randmac,note,personal\n"
        "VS1,arm,RName1,1.1.1.1,aa,,Extra,true\n"
        "VS2,mkp,RName2,2.2.2.2,bb,,Extra,false\n",
        encoding="utf-8",
    )

    gr = importlib.import_module("scripts.generate_report1")
    monkeypatch.setattr(gr, "BASE_DIR", base_dir)
    gr.main()

    report_path = base_dir / "data" / "result" / "report1.csv"
    with open(report_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert (
        rows[0]["note"]
        == "Надано на перевірку. Пристрій особистий. Заявка на підключення до локальних мереж, складена, МАС-адреса закріплена за ІР-адресою."
    )
    assert (
        rows[1]["note"]
        == "Надано на перевірку. Пристрій службовий. Заявка на підключення до локальних мереж, складена, МАС-адреса закріплена за ІР-адресою."
    )
    assert rows[0]["ownership"] == "особистий"
    assert rows[1]["ownership"] == "службовий"
    assert rows[0]["informsystem"] == "none"
    assert rows[1]["informsystem"] == "none"
