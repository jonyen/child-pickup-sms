from datetime import date
from unittest.mock import MagicMock
from child_pickup.pickup_schedule import (
    find_date_column_index,
    read_blank_rows,
    group_blank_rows,
)
from child_pickup.kids_info import KidInfo


HEADERS = ["Last Name", "Full Name", "ON-GOING", "4/12", "4/19", "4/26"]


def test_find_date_column_index():
    assert find_date_column_index(HEADERS, date(2026, 4, 12)) == 3
    assert find_date_column_index(HEADERS, date(2026, 4, 19)) == 4


def test_find_date_column_index_missing():
    assert find_date_column_index(HEADERS, date(2026, 5, 3)) is None


def test_read_blank_rows_returns_only_blank_cells():
    rows = [
        HEADERS,
        ["Chow", "Estelle Chow", "Jenny or Alan", "Jenny/Alan", "", ""],
        ["Shim", "Caden Shim", "Hanseul or Deandra", "", "", ""],
        ["Shim", "Easton Shim", "Hanseul or Deandra", "", "", ""],
        ["Lee", "Alden Lee", "Bliss or Liny", "", "", ""],
    ]
    children = read_blank_rows(rows, col_index=3)
    names = [c.full_name for c in children]
    assert "Estelle Chow" not in names  # filled, skip
    assert names == ["Caden Shim", "Easton Shim", "Alden Lee"]
    assert children[0].row_number == 3  # 1-indexed; header row=1, Chow row=2
    assert children[0].ongoing_person == "Hanseul or Deandra"


def test_group_blank_rows_groups_by_ongoing_and_dedupes_phones():
    children = [
        _child("Caden Shim", 3, "Hanseul or Deandra"),
        _child("Easton Shim", 4, "Hanseul or Deandra"),
        _child("Alden Lee", 5, "Bliss or Liny"),
    ]
    kids_info = {
        "Caden Shim": KidInfo("Caden Shim", "Deandra Shim", "+15551110000",
                              "Hanseul Shim", "+15552220000"),
        "Easton Shim": KidInfo("Easton Shim", "Deandra Shim", "+15551110000",
                               "Hanseul Shim", "+15552220000"),
        "Alden Lee": KidInfo("Alden Lee", "Liny Lee", "+15553330000",
                             "Bliss Lee", "+15554440000"),
    }
    groups = group_blank_rows(children, kids_info)
    assert len(groups) == 2
    shim = next(g for g in groups if g.ongoing_person == "Hanseul or Deandra")
    assert shim.unique_phones() == ["+15551110000", "+15552220000"]
    assert sorted(shim.child_names()) == ["Caden Shim", "Easton Shim"]
    assert set(shim.parent_names) == {"Deandra Shim", "Hanseul Shim"}


def test_group_skips_children_with_no_phones():
    children = [_child("Ghost Kid", 10, "Nobody")]
    kids_info = {"Ghost Kid": KidInfo("Ghost Kid", "", None, "", None)}
    groups = group_blank_rows(children, kids_info)
    assert groups == []


def _child(name, row, ongoing):
    from child_pickup.models import Child
    last = name.split()[-1]
    return Child(full_name=name, last_name=last, row_number=row, ongoing_person=ongoing)
