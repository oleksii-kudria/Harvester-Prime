from pathlib import Path
import importlib
import sys
import types


def test_normalize_note_handles_empty_and_nonempty_target():
    base_dir = Path(__file__).resolve().parent.parent
    config_file = base_dir / "configs" / "local.yml"
    config_file.write_text(
        """apps:
  empty_app:
    source: "XY"
    target: ""
  value_app:
    source: "AB"
    target: "NewValue"
""",
        encoding="utf-8",
    )

    try:
        sys.modules.pop("scripts.process", None)
        sys.modules.setdefault("pandas", types.ModuleType("pandas"))
        dummy_yaml = types.ModuleType("yaml")
        dummy_yaml.safe_load = lambda stream: {
            "apps": {
                "empty_app": {"source": "XY", "target": ""},
                "value_app": {"source": "AB", "target": "NewValue"},
            }
        }
        sys.modules.setdefault("yaml", dummy_yaml)
        process = importlib.import_module("scripts.process")
        assert process.normalize_note("XY") == ""
        assert process.normalize_note("xy") == ""
        assert process.normalize_note("AB") == "NewValue"
        assert process.normalize_note("ab") == "NewValue"
        assert process.normalize_note("other") == "other"
    finally:
        config_file.unlink()
        sys.modules.pop("scripts.process", None)
        sys.modules.pop("pandas", None)
        sys.modules.pop("yaml", None)

