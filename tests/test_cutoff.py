from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.cutoff import run_cutoff_flow
from child_pickup.email_client import SummaryData


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
         "Deandra Shim", "+15551110000", "Hanseul Shim", "+15552220000",
         "", "", "", "", ""],
        ["", "", "", "Easton Shim", "M", "", "",
         "Deandra Shim", "+15551110000", "Hanseul Shim", "+15552220000",
         "", "", "", "", ""],
        ["", "", "", "Alden Lee", "M", "", "",
         "Liny Lee", "+15553330000", "Bliss Lee", "+15554440000",
         "", "", "", "", ""],
    ]


def test_cutoff_writes_no_response_for_blank_rows():
    pickup_rows = [
        ["Last Name", "Full Name", "ON-GOING", "4/12"],
        ["Chow", "Estelle Chow", "Jenny or Alan", "Jenny or Alan"],  # confirmed
        ["Shim", "Caden Shim", "Hanseul or Deandra", ""],  # blank → no response
        ["Shim", "Easton Shim", "Hanseul or Deandra", ""],  # blank → no response
        ["Lee", "Alden Lee", "Bliss or Liny", "Grandma"],  # changed
    ]
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": pickup_rows,
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]
    email = MagicMock()

    run_cutoff_flow(
        sheets=sheets,
        email=email,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pickup_col_index=3,
        target_date=date(2026, 4, 12),
        now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
    )

    # NO RESPONSE written to D3 and D4
    update_calls = sheets.update_range.call_args_list
    ranges = [c.args[0] for c in update_calls]
    assert "'Pickup Schedule'!D3" in ranges
    assert "'Pickup Schedule'!D4" in ranges
    for c in update_calls:
        assert c.args[1] == [["NO RESPONSE"]]

    email.send_summary.assert_called_once()
    data: SummaryData = email.send_summary.call_args.args[0]
    assert data.pickup_date == date(2026, 4, 12)
    assert len(data.confirmed) == 1
    assert data.confirmed[0].pickup_person == "Jenny or Alan"
    assert len(data.changed) == 1
    assert data.changed[0].pickup_person == "Grandma"
    assert data.changed[0].original_ongoing == "Bliss or Liny"
    assert len(data.no_response) == 2


def test_cutoff_categorizes_absent_separately():
    pickup_rows = [
        ["Last Name", "Full Name", "ON-GOING", "4/12"],
        ["Chow", "Estelle Chow", "Jenny or Alan", "Jenny or Alan"],  # confirmed
        ["Shim", "Caden Shim", "Hanseul or Deandra", "ABSENT"],  # absent
        ["Shim", "Easton Shim", "Hanseul or Deandra", "ABSENT"],  # absent
        ["Lee", "Alden Lee", "Bliss or Liny", ""],  # blank → no response
    ]
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": pickup_rows,
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]
    email = MagicMock()

    run_cutoff_flow(
        sheets=sheets,
        email=email,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pickup_col_index=3,
        target_date=date(2026, 4, 12),
        now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
    )

    email.send_summary.assert_called_once()
    data: SummaryData = email.send_summary.call_args.args[0]
    assert len(data.confirmed) == 1
    assert len(data.absent) == 2
    assert len(data.no_response) == 1
    assert len(data.changed) == 0


def test_cutoff_still_emails_when_all_resolved():
    pickup_rows = [
        ["Last Name", "Full Name", "ON-GOING", "4/12"],
        ["Chow", "Estelle Chow", "Jenny or Alan", "Jenny or Alan"],
    ]
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": pickup_rows,
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]
    email = MagicMock()

    run_cutoff_flow(
        sheets=sheets,
        email=email,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pickup_col_index=3,
        target_date=date(2026, 4, 12),
        now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
    )

    email.send_summary.assert_called_once()
    sheets.update_range.assert_not_called()
