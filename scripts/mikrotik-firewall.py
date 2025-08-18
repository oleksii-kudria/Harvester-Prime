#!/usr/bin/env python3
"""Generate Mikrotik firewall rules and DHCP static lease commands."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent


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
    """Return True if *text* contains any Cyrillic characters."""
    return bool(re.search("[\u0400-\u04FF]", text))


def transliterate(text: str) -> str:
    """Return *text* transliterated to Latin characters."""
    try:  # Use unidecode if available for broader coverage
        from unidecode import unidecode  # type: ignore
        return unidecode(text)
    except Exception:  # pragma: no cover - fallback rarely used in tests
        return "".join(TRANSLIT_MAP.get(ch, ch) for ch in text)


def process_values(rows: Iterable[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    """Process *rows* ensuring name and owner are transliterated if needed."""
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
    """Read CSV file and return list of rows with string values."""
    rows: List[dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({k: (v or "") for k, v in row.items()})
    return rows


def main() -> None:
    verified_path = BASE_DIR / "data" / "interim" / "verified.csv"
    if not verified_path.exists():
        print(f"Файл {verified_path} не знайдено")
        sys.exit(1)

    rows = read_rows(verified_path)
    sources = sorted({row.get("source", "") for row in rows if row.get("source", "")})
    if not sources:
        print("Стовпець 'source' порожній")
        sys.exit(1)

    for idx, src in enumerate(sources, start=1):
        print(f"{idx}. {src}")
    try:
        choice = int(input("Оберіть джерело за номером: "))
        source_value = sources[choice - 1]
    except (ValueError, IndexError):
        print("Невірний вибір")
        sys.exit(1)

    subset = [
        (row.get("ip", ""), row.get("name", ""), row.get("owner", ""))
        for row in rows
        if row.get("source", "") == source_value
    ]
    records = process_values(subset)

    result_dir = BASE_DIR / "data" / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    out_path = result_dir / f"mikrotik-firewall-{source_value}.txt"

    with open(out_path, "w", encoding="utf-8") as fh:
        for ip, name, owner in records:
            fh.write(
                f"/ip firewall address-list add address={ip} comment=\"{name}, {owner}\" list=trusted_list\n"
            )
        for ip, name, owner in records:
            fh.write(f"/ip dhcp-server lease make-static [find address={ip}]\n")
            fh.write(
                f"/ip dhcp-server lease comment comment=\"{name}, {owner}\" [find address={ip}]\n"
            )

    print(f"Створено файл {out_path}")


if __name__ == "__main__":
    main()
