"""Helpers for working with column mapping schemas."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml

from app.io.csvio import read_csv


def load_schemas(path: str = "configs/schemas.yml") -> Dict[str, Dict[str, str]]:
    """Load column mapping definitions."""

    schema_path = Path(path)
    if not schema_path.exists():
        return {}
    with open(schema_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


SCHEMAS = load_schemas()


def read_csv_mapped(path: Path, schema_key: str, columns: List[str]) -> List[Dict[str, str]]:
    """Read CSV applying column mapping for *schema_key* and returning *columns*."""

    mapping = SCHEMAS.get(schema_key, {})
    rows = read_csv(path)
    remapped: List[Dict[str, str]] = []
    for row in rows:
        # some files may use "hostname" instead of "name"
        if "name" in columns and "name" not in row:
            row["name"] = row.get("hostname", "")
        remapped.append({col: row.get(mapping.get(col, col), "") for col in columns})
    return remapped


__all__ = ["SCHEMAS", "load_schemas", "read_csv_mapped"]
