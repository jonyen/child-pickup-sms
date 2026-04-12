from __future__ import annotations
from datetime import date, timedelta
from typing import Optional

from .models import Child, Group
from .kids_info import KidInfo


def find_date_column_index(headers: list[str], target: date) -> Optional[int]:
    """Return 0-indexed column for the target date, or None if not found.

    Sheet headers use M/D format without zero padding (e.g. '4/12').
    """
    target_str = f"{target.month}/{target.day}"
    for i, h in enumerate(headers):
        if str(h).strip() == target_str:
            return i
    return None


def _parse_row(row: list[str], col_index: int, sheet_row_idx: int):
    """Parse a data row into (Child, cell_value) or None if row is invalid."""
    if len(row) < 3:
        return None
    last_name = row[0].strip() if row[0] else ""
    full_name = row[1].strip() if row[1] else ""
    ongoing = row[2].strip() if row[2] else ""
    if not full_name:
        return None
    cell = row[col_index].strip() if col_index < len(row) and row[col_index] else ""
    child = Child(
        full_name=full_name,
        last_name=last_name,
        row_number=sheet_row_idx,
        ongoing_person=ongoing,
    )
    return child, cell


def read_blank_rows(rows: list[list[str]], col_index: int) -> list[Child]:
    """Return Child records for rows where the target column is blank."""
    out: list[Child] = []
    for sheet_row_idx, row in enumerate(rows[1:], start=2):
        parsed = _parse_row(row, col_index, sheet_row_idx)
        if parsed is None:
            continue
        child, cell = parsed
        if not cell:
            out.append(child)
    return out


def read_filled_rows(rows: list[list[str]], col_index: int) -> list[tuple[Child, str]]:
    """Return (Child, cell_value) for rows where the target column is filled."""
    out: list[tuple[Child, str]] = []
    for sheet_row_idx, row in enumerate(rows[1:], start=2):
        parsed = _parse_row(row, col_index, sheet_row_idx)
        if parsed is None:
            continue
        child, cell = parsed
        if cell:
            out.append((child, cell))
    return out


def find_children_for_phone(
    blank_children: list[Child],
    kids_info: dict[str, KidInfo],
    phone: str,
) -> list[Child]:
    """Find blank-row children whose parents include the given phone number."""
    matching: list[Child] = []
    for child in blank_children:
        info = kids_info.get(child.full_name)
        if not info:
            continue
        if phone in (info.mother_phone, info.father_phone):
            matching.append(child)
    return matching


def group_blank_rows(
    children: list[Child], kids_info: dict[str, KidInfo]
) -> list[Group]:
    """Group children by ongoing_person, then collect parent phones from kids_info.

    Drops groups where no parent phones could be resolved.
    """
    by_ongoing: dict[str, list[Child]] = {}
    for c in children:
        by_ongoing.setdefault(c.ongoing_person, []).append(c)

    groups: list[Group] = []
    for ongoing, kids in by_ongoing.items():
        phones: list[str] = []
        names: list[str] = []
        for c in kids:
            info = kids_info.get(c.full_name)
            if not info:
                continue
            for phone, pname in (
                (info.mother_phone, info.mother_name),
                (info.father_phone, info.father_name),
            ):
                if phone:
                    phones.append(phone)
                    names.append(pname or "")
        if not phones:
            continue
        groups.append(
            Group(
                ongoing_person=ongoing,
                children=kids,
                parent_phones=phones,
                parent_names=names,
            )
        )
    return groups


def ensure_next_week_column(
    sheets, pickup_tab: str, headers: list[str], target_date: date
) -> None:
    """Add a column header for next week's date if it doesn't already exist."""
    next_week = target_date + timedelta(days=7)
    next_week_str = f"{next_week.month}/{next_week.day}"
    for h in headers:
        if str(h).strip() == next_week_str:
            return
    col_index = len(headers)
    col_letter = chr(ord("A") + col_index)
    sheets.update_range(f"'{pickup_tab}'!{col_letter}1", [[next_week_str]])
