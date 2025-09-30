"""Functions for normalizing DHCP log data."""
from __future__ import annotations

from collections import Counter
import re
from typing import Dict, Iterable, List

PAYLOAD_RE = re.compile(
    r"assigned\s+(?P<ip>\d+\.\d+\.\d+\.\d+)\s+for\s+(?P<mac>[0-9A-Fa-f:]{17})(?:\s+(?P<hostname>[^\s]+))?"
)


def _mac_key(value: str) -> str:
    """Return a normalised key for *value* suitable for grouping."""

    hex_only = re.sub(r"[^0-9A-Fa-f]", "", value or "").upper()
    return hex_only or (value or "").strip().upper()


def _format_mac(value: str) -> str:
    """Return *value* formatted as ``XX:XX:XX:XX:XX:XX`` when possible."""

    hex_only = re.sub(r"[^0-9A-Fa-f]", "", value or "").upper()
    if len(hex_only) != 12:
        return (value or "").strip()
    return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2))


def is_randomized_mac(value: str) -> bool:
    """Return ``True`` if *value* is a locally administered MAC address."""

    hex_only = re.sub(r"[^0-9A-Fa-f]", "", value or "")
    if len(hex_only) < 2:
        return False
    try:
        first_octet = int(hex_only[:2], 16)
    except ValueError:
        return False
    return bool(first_octet & 0x02)


def parse_payload(payload: str) -> Dict[str, str]:
    """Extract IP, MAC and hostname from a payload string."""
    match = PAYLOAD_RE.search(payload or "")
    if not match:
        return {"ip": "", "mac": "", "hostname": "unknown"}
    info = match.groupdict()
    if not info.get("hostname"):
        info["hostname"] = "unknown"
    return info


def deduplicate_by_mac(records: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """Return only the latest record for each MAC address."""
    latest: Dict[str, Dict[str, str]] = {}
    for record in records:
        mac = _mac_key(record.get("sourcMACAddress", ""))
        time_str = record.get("deviceTime", "0")
        try:
            timestamp = int(time_str)
        except ValueError:
            timestamp = 0
        stored = latest.get(mac)
        if stored is None or timestamp > int(stored.get("deviceTime", 0)):
            latest[mac] = record
    return list(latest.values())


def normalize_dhcp_records(records: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """Normalize raw DHCP log records for downstream processing.

    The resulting dictionaries contain the following fields:

    ``source``
        Identifier of the log source.
    ``ip``
        Assigned IP address.
    ``mac``
        MAC address of the client device.
    ``hostname``
        Hostname extracted from the payload (or ``"unknown"``).
    ``firstDate``
        Earliest ``deviceTime`` for the MAC address across all records.
    ``lastDate``
        Latest ``deviceTime`` for the MAC address.
    """

    # ``records`` may be an iterator; convert to list so we can iterate twice
    records = list(records)

    # Determine the earliest timestamp and occurrence count for each MAC address
    first_seen: Dict[str, str] = {}
    occurrences: Counter[str] = Counter()
    for record in records:
        mac_key = _mac_key(record.get("sourcMACAddress", ""))
        time_str = record.get("deviceTime", "0")
        try:
            ts = int(time_str)
        except ValueError:
            ts = 0
        if mac_key not in first_seen or ts < int(first_seen.get(mac_key, ts)):
            first_seen[mac_key] = time_str
        occurrences[mac_key] += 1

    normalized: List[Dict[str, str]] = []
    for record in deduplicate_by_mac(records):
        payload = parse_payload(record.get("payloadAsUTF", ""))
        mac = _format_mac(payload.get("mac", record.get("sourcMACAddress", "")))
        mac_key = _mac_key(mac)
        normalized.append(
            {
                "source": record.get("logSourceIdentifier", ""),
                "ip": payload.get("ip", ""),
                "mac": mac,
                "hostname": payload.get("hostname", "unknown"),
                "firstDate": first_seen.get(mac_key, ""),
                "lastDate": record.get("deviceTime", ""),
                "count": str(occurrences.get(mac_key, 0)),
                "randomized": "true" if is_randomized_mac(mac) else "false",
            }
        )
    return normalized
