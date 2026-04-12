from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class KidInfo:
    full_name: str
    mother_name: str
    mother_phone: Optional[str]
    father_name: str
    father_phone: Optional[str]


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    # Fallback: return whatever we got, prefixed with +
    return "+" + digits


REQUIRED_HEADERS = {
    "Name (First & Last)": "full_name",
    "Mother": "mother_name",
    "Mother's phone #": "mother_phone",
    "Father": "father_name",
    "Father's phone #": "father_phone",
}


def load_kids_info(sheets_client, tab_name: str) -> dict[str, KidInfo]:
    rows = sheets_client.read_range(f"'{tab_name}'!A1:Z1000")
    if not rows:
        return {}
    headers = rows[0]
    try:
        idx = {label: headers.index(label) for label in REQUIRED_HEADERS}
    except ValueError as e:
        raise ValueError(f"KidsInfo tab missing required header: {e}")

    out: dict[str, KidInfo] = {}
    for row in rows[1:]:
        if len(row) <= idx["Name (First & Last)"]:
            continue
        full_name = row[idx["Name (First & Last)"]].strip()
        if not full_name:
            continue
        out[full_name] = KidInfo(
            full_name=full_name,
            mother_name=_get(row, idx["Mother"]),
            mother_phone=normalize_phone(_get(row, idx["Mother's phone #"])),
            father_name=_get(row, idx["Father"]),
            father_phone=normalize_phone(_get(row, idx["Father's phone #"])),
        )
    return out


def _get(row: list, idx: int) -> str:
    return row[idx].strip() if idx < len(row) and row[idx] else ""
