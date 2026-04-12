# tests/test_send.py
from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.send import run_send_flow


def _pickup_rows():
    return [
        ["Last Name", "Full Name", "ON-GOING", "4/12", "4/19"],
        ["Chow", "Estelle Chow", "Jenny or Alan", "Jenny/Alan", ""],
        ["Shim", "Caden Shim", "Hanseul or Deandra", "", ""],
        ["Shim", "Easton Shim", "Hanseul or Deandra", "", ""],
        ["Lee", "Alden Lee", "Bliss or Liny", "", ""],
    ]


def _kids_info_rows():
    headers = [
        "City", "Ministry Group", "Domain",
        "Name (First & Last)", "Gender", "Bday", "Age",
        "Mother", "Mother's phone #", "Father", "Father's phone #",
        "Allergy", "Desc", "Symp", "Treat", "Ins",
    ]
    return [
        headers,
        ["", "", "", "Caden Shim", "M", "", "",
         "Deandra Shim", "555-111-1111", "Hanseul Shim", "555-222-2222",
         "", "", "", "", ""],
        ["", "", "", "Easton Shim", "M", "", "",
         "Deandra Shim", "555-111-1111", "Hanseul Shim", "555-222-2222",
         "", "", "", "", ""],
        ["", "", "", "Alden Lee", "M", "", "",
         "Liny Lee", "555-333-3333", "Bliss Lee", "555-444-4444",
         "", "", "", "", ""],
    ]


def test_send_flow_sends_groups():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]

    twilio = MagicMock()
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        target_date=date(2026, 4, 12),
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
    )

    # Two groups: Shim (2 kids, 2 parents) and Lee (1 kid, 2 parents)
    assert result.groups_sent == 2
    assert twilio.send.call_count == 4  # 2 groups * 2 parents


def test_send_flow_ensures_next_week_column():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]

    twilio = MagicMock()
    run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        target_date=date(2026, 4, 12),
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
    )

    # 4/19 already exists in headers, so no new column should be added.
    # But next week after 4/19 is 4/26 — not in headers. However, we process
    # target 4/12, so next week = 4/19 which IS in headers → no update_range for header.
    # The update_range calls should only be for blank rows (not header).
    # Actually the send flow doesn't write to cells at all — only twilio.send.
    # ensure_next_week_column should NOT write because 4/19 is already there.
    header_writes = [
        c for c in sheets.update_range.call_args_list
        if "1" in c.args[0] and c.args[0].endswith("1")
    ]
    assert len(header_writes) == 0


def test_send_flow_creates_next_week_column_when_missing():
    rows = [
        ["Last Name", "Full Name", "ON-GOING", "4/12"],
        ["Shim", "Caden Shim", "Hanseul or Deandra", ""],
    ]
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": rows,
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]

    twilio = MagicMock()
    run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        target_date=date(2026, 4, 12),
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
    )

    # Next week 4/19 not in headers → should write E1 = "4/19"
    sheets.update_range.assert_any_call("'Pickup Schedule'!E1", [["4/19"]])


def test_send_flow_aborts_if_column_missing():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]
    twilio = MagicMock()
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        target_date=date(2026, 5, 3),  # not in headers
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 5, 2, 21, 0, tzinfo=timezone.utc),
    )
    assert result.aborted is True
    twilio.send.assert_not_called()
