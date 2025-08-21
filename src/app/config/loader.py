"""Functions for loading application configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Set

import yaml

from app.utils.mac import normalize, MAC_RE


def load_local_config(path: str = "configs/local.yml") -> Dict:
    """Load local configuration file if it exists."""

    config_path = Path(path)
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_base_config(path: str = "configs/base.yaml") -> Dict:
    """Load base configuration file."""

    config_path = Path(path)
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def ignored_macs(path: str = "configs/local.yml") -> Set[str]:
    """Return set of normalised MAC addresses configured to be ignored."""

    config = load_local_config(path)
    macs: Set[str] = set()
    for value in ((config.get("ignore") or {}).get("mac") or {}).values():
        mac_norm = normalize(str(value))
        if MAC_RE.fullmatch(mac_norm):
            macs.add(mac_norm)
    return macs


def note_mapping(path: str = "configs/local.yml") -> Dict[str, str]:
    """Return mapping for note normalisation from configuration."""

    config = load_local_config(path)
    mapping: Dict[str, str] = {}
    for app in (config.get("apps") or {}).values():
        source = (app.get("source") or "").strip()
        target = app.get("target")
        if source and target is not None:
            mapping[source.lower()] = target
    return mapping


__all__ = [
    "load_local_config",
    "load_base_config",
    "ignored_macs",
    "note_mapping",
]
