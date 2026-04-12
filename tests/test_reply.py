from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.reply import handle_reply
from child_pickup.parser import ParseResult


def _pickup_rows():
    return [
        ["Last Name", "Full Name", "ON-GOING", "4/12"],
        ["Chow", "Estelle Chow", "Jenny or Alan", "Jenny/Alan"],
        ["Shim", "Caden Shim", "Hanseul or Deandra", ""],
        ["Shim", "Easton Shim", "Hanseul or Deandra", ""],
        ["Lee", "Alden Lee", "Bliss or Liny", ""],
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
         "Deandra Shim", "+15551110000", "Hanseul Shim", "+15552220000",
         "", "", "", "", ""],
        ["", "", "", "Easton Shim", "M", "", "",
         "Deandra Shim", "+15551110000", "Hanseul Shim", "+15552220000",
         "", "", "", "", ""],
        ["", "", "", "Alden Lee", "M", "", "",
         "Liny Lee", "+15553330000", "Bliss Lee", "+15554440000",
         "", "", "", "", ""],
    ]


def test_confirm_writes_ongoing_person_to_cells():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="confirm")

    outcome = handle_reply(
        sheets=sheets,
        parser=parser,
        from_phone="+15551110000",
        body="yes",
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "confirm"
    # ON-GOING person written to D3 and D4 (Shim siblings)
    calls = sheets.update_range.call_args_list
    ranges = [c.args[0] for c in calls]
    assert "'Pickup Schedule'!D3" in ranges
    assert "'Pickup Schedule'!D4" in ranges
    for c in calls:
        assert c.args[1] == [["Hanseul or Deandra"]]


def test_change_writes_new_name_to_cells():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="change", new_pickup_person="Grandma Linda")

    outcome = handle_reply(
        sheets=sheets,
        parser=parser,
        from_phone="+15551110000",
        body="my mom Linda",
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "change"
    for c in sheets.update_range.call_args_list:
        assert c.args[1] == [["Grandma Linda"]]


def test_ambiguous_leaves_row_blank_and_returns_reply_text():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="ambiguous")

    outcome = handle_reply(
        sheets=sheets,
        parser=parser,
        from_phone="+15551110000",
        body="huh?",
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "ambiguous"
    # No cells written (only read_range calls)
    update_calls = [c for c in sheets.update_range.call_args_list]
    assert len(update_calls) == 0
    assert "Hanseul or Deandra" in outcome.reply_text


def test_no_matching_children_returns_unmatched():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
    }[rng]
    parser = MagicMock()

    outcome = handle_reply(
        sheets=sheets,
        parser=parser,
        from_phone="+15559999999",  # unknown number
        body="yes",
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "unmatched"
    assert "don't have a pending" in outcome.reply_text.lower()
    parser.parse.assert_not_called()
