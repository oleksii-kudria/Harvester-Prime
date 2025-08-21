"""Generate Mikrotik firewall rules from verified CSV data."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable, List, Tuple

TRANSLIT_MAP = {
    "А": "A", "а": "a",
    "Б": "B", "б": "b",
    "В": "V", "в": "v",
    "Г": "H", "г": "h",
    "Ґ": "G", "ґ": "g",
    "Д": "D", "д": "d",
    "Е": "E", "е": "e",
    "Є": "Ye", "є": "ie",
    "Ж": "Zh", "ж": "zh",
    "З": "Z", "з": "z",
    "И": "Y", "и": "y",
    "І": "I", "і": "i",
    "Ї": "Yi", "ї": "i",
    "Й": "Y", "й": "y",
    "К": "K", "к": "k",
    "Л": "L", "л": "l",
    "М": "M", "м": "m",
    "Н": "N", "н": "n",
    "О": "O", "о": "o",
    "П": "P", "п": "p",
    "Р": "R", "р": "r",
    "С": "S", "с": "s",
    "Т": "T", "т": "t",
    "У": "U", "у": "u",
    "Ф": "F", "ф": "f",
    "Х": "Kh", "х": "kh",
    "Ц": "Ts", "ц": "ts",
    "Ч": "Ch", "ч": "ch",
    "Ш": "Sh", "ш": "sh",
    "Щ": "Shch", "щ": "shch",
    "Ъ": "", "ъ": "",
    "Ы": "Y", "ы": "y",
    "Ь": "", "ь": "",
    "Э": "E", "э": "e",
    "Ю": "Yu", "ю": "yu",
    "Я": "Ya", "я": "ya",
    "Ё": "Yo", "ё": "yo",
}


def contains_cyrillic(text: str) -> bool:
    return bool(re.search("[\u0400-\u04FF]", text))


def transliterate(text: str) -> str:
    try:
        from unidecode import unidecode  # type: ignore
        return unidecode(text)
    except Exception:  # pragma: no cover
        return "".join(TRANSLIT_MAP.get(ch, ch) for ch in text)


def process_values(rows: Iterable[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    processed: List[Tuple[str, str, str]] = []
    for ip, name, owner in rows:
        name = name.strip()
        owner = owner.strip()
        if contains_cyrillic(name):
            name = transliterate(name)
        if contains_cyrillic(owner):
            owner = transliterate(owner)
        processed.append((ip.strip(), name, owner))
    return processed


def read_rows(path: Path) -> List[dict[str, str]]:
    rows: List[dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({k: (v or "") for k, v in row.items()})
    return rows


def generate_commands(rows: Iterable[Tuple[str, str, str]], out_path: Path) -> None:
    with open(out_path, "w", encoding="utf-8") as fh:
        for ip, name, owner in rows:
            fh.write(
                f"/ip firewall address-list add address={ip} comment=\"{name}, {owner}\" list=trusted_list\n"
            )
        for ip, name, owner in rows:
            fh.write(f"/ip dhcp-server lease make-static [find address={ip}]\n")
            fh.write(
                f"/ip dhcp-server lease comment comment=\"{name}, {owner}\" [find address={ip}]\n"
            )


def build_firewall(source: str, verified_path: Path, out_path: Path) -> None:
    rows = read_rows(verified_path)
    subset = [
        (row.get("ip", ""), row.get("name", ""), row.get("owner", ""))
        for row in rows
        if row.get("source", "") == source
    ]
    records = process_values(subset)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    generate_commands(records, out_path)


__all__ = [
    "read_rows",
    "process_values",
    "build_firewall",
]
