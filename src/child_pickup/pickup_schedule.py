from __future__ import annotations
from datetime import date
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


def read_blank_rows(rows: list[list[str]], col_index: int) -> list[Child]:
    """Given raw sheet rows (first row is headers), return Child records
    for rows where the target column is blank.

    Assumes columns: Last Name=0, Full Name=1, ON-GOING=2, then date columns.
    Header row is row 1 (1-indexed); data starts at row 2.
    """
    out: list[Child] = []
    for sheet_row_idx, row in enumerate(rows[1:], start=2):
        if len(row) < 3:
            continue
        last_name = row[0].strip() if row[0] else ""
        full_name = row[1].strip() if row[1] else ""
        ongoing = row[2].strip() if row[2] else ""
        if not full_name:
            continue
        cell = row[col_index].strip() if col_index < len(row) and row[col_index] else ""
        if cell:
            continue  # already filled; skip
        out.append(
            Child(
                full_name=full_name,
                last_name=last_name,
                row_number=sheet_row_idx,
                ongoing_person=ongoing,
            )
        )
    return out


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
