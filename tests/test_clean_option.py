import os
from pathlib import Path

from scripts import process


def test_clean_interim(tmp_path):
    interim = tmp_path / "interim"
    interim.mkdir()
    to_remove = interim / "remove.csv"
    to_remove.write_text("data")
    to_keep = interim / "keep.example.csv"
    to_keep.write_text("data")

    process.clean_interim(interim)

    assert not to_remove.exists()
    assert to_keep.exists()

    # Should not raise when nothing to remove
    process.clean_interim(interim)
    assert to_keep.exists()
