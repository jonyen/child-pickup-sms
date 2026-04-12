from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.reply import handle_reply, ReplyOutcome
from child_pickup.models import PendingConfirmation
from child_pickup.parser import ParseResult


def _make_pending():
    return PendingConfirmation(
        id="id-1",
        sent_at=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
        pickup_date=date(2026, 4, 12),
        sheet_row_numbers=[3, 4],
        children_names=["Caden Shim", "Easton Shim"],
        ongoing_person="Hanseul or Deandra",
        parent_phones=["+15551110000", "+15552220000"],
        parent_names=["Hanseul Shim", "Deandra Shim"],
        status="pending",
    )


def test_confirm_writes_blank_and_marks_confirmed():
    store = MagicMock()
    store.find_pending_for_phone.return_value = _make_pending()
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="confirm")
    sheets = MagicMock()

    outcome = handle_reply(
        sheets=sheets,
        store=store,
        parser=parser,
        from_phone="+15551110000",
        body="yes",
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,  # '4/12' column (0-indexed: D)
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "confirm"
    # Blank written to D3 and D4
    calls = sheets.update_range.call_args_list
    ranges = [c.args[0] for c in calls]
    assert "'Pickup Schedule'!D3" in ranges
    assert "'Pickup Schedule'!D4" in ranges
    for c in calls:
        assert c.args[1] == [[""]]
    store.mark_resolved.assert_called_once()
    assert store.mark_resolved.call_args.kwargs["status"] == "confirmed"


def test_change_writes_new_name_to_cells():
    store = MagicMock()
    store.find_pending_for_phone.return_value = _make_pending()
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="change", new_pickup_person="Grandma Linda")
    sheets = MagicMock()

    outcome = handle_reply(
        sheets=sheets,
        store=store,
        parser=parser,
        from_phone="+15551110000",
        body="my mom Linda",
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "change"
    for c in sheets.update_range.call_args_list:
        assert c.args[1] == [["Grandma Linda"]]
    assert store.mark_resolved.call_args.kwargs["status"] == "changed"
    assert store.mark_resolved.call_args.kwargs["resolved_value"] == "Grandma Linda"


def test_ambiguous_leaves_row_pending_and_returns_reply_text():
    store = MagicMock()
    store.find_pending_for_phone.return_value = _make_pending()
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="ambiguous")
    sheets = MagicMock()

    outcome = handle_reply(
        sheets=sheets,
        store=store,
        parser=parser,
        from_phone="+15551110000",
        body="huh?",
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "ambiguous"
    sheets.update_range.assert_not_called()
    store.mark_resolved.assert_not_called()
    assert "Hanseul or Deandra" in outcome.reply_text


def test_no_matching_pending_returns_unmatched():
    store = MagicMock()
    store.find_pending_for_phone.return_value = None
    parser = MagicMock()
    outcome = handle_reply(
        sheets=MagicMock(),
        store=store,
        parser=parser,
        from_phone="+15559999999",
        body="yes",
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )
    assert outcome.action == "unmatched"
    assert "don't have a pending" in outcome.reply_text.lower()
    parser.parse.assert_not_called()
