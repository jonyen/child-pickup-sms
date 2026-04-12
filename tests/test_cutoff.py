from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.cutoff import run_cutoff_flow
from child_pickup.models import PendingConfirmation
from child_pickup.email_client import SummaryData


def _pending(id, status):
    return PendingConfirmation(
        id=id,
        sent_at=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
        pickup_date=date(2026, 4, 12),
        sheet_row_numbers=[3, 4],
        children_names=["Caden Shim", "Easton Shim"],
        ongoing_person="Hanseul or Deandra",
        parent_phones=["+15551110000"],
        parent_names=["Hanseul Shim"],
        status=status,
    )


def test_cutoff_writes_no_response_and_marks_rows():
    sheets = MagicMock()
    store = MagicMock()
    store.list_pending.return_value = [_pending("id-1", "pending")]
    # Also provide full history for the summary
    store._read_all.return_value = [
        (2, _pending("id-confirmed", "confirmed")),
        (3, _pending("id-1", "no_response")),  # after update
    ]
    store.get_send_errors.return_value = ["no phones for Ghost Kid"]
    email = MagicMock()

    result = run_cutoff_flow(
        sheets=sheets,
        store=store,
        email=email,
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        target_date=date(2026, 4, 12),
        now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
    )

    # Wrote NO RESPONSE to D3 and D4
    ranges = [c.args[0] for c in sheets.update_range.call_args_list]
    assert "'Pickup Schedule'!D3" in ranges
    assert "'Pickup Schedule'!D4" in ranges
    for c in sheets.update_range.call_args_list:
        assert c.args[1] == [["NO RESPONSE"]]

    store.mark_resolved.assert_called_once()
    assert store.mark_resolved.call_args.kwargs["status"] == "no_response"
    assert store.mark_resolved.call_args.kwargs["resolved_value"] == "NO RESPONSE"

    email.send_summary.assert_called_once()
    data: SummaryData = email.send_summary.call_args.args[0]
    assert data.pickup_date == date(2026, 4, 12)
    assert "no phones for Ghost Kid" in data.send_errors


def test_cutoff_still_emails_when_no_pending():
    sheets = MagicMock()
    store = MagicMock()
    store.list_pending.return_value = []
    store._read_all.return_value = []
    store.get_send_errors.return_value = []
    email = MagicMock()

    run_cutoff_flow(
        sheets=sheets,
        store=store,
        email=email,
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        target_date=date(2026, 4, 12),
        now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
    )
    email.send_summary.assert_called_once()
    sheets.update_range.assert_not_called()
