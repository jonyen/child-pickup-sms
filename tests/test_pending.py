# tests/test_pending.py
from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.pending import PendingStore
from child_pickup.models import PendingConfirmation


def test_list_pending_for_date_filters_by_date_and_status():
    sheets = MagicMock()
    sheets.read_range.return_value = [
        PendingConfirmation.SHEET_HEADERS,
        [
            "id-1", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "3,4", "Caden Shim,Easton Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
        [
            "id-2", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "5", "Alden Lee", "Bliss or Liny",
            "+15552220000", "Bliss Lee", "confirmed",
            "2026-04-11T22:00:00+00:00", "yes", "",
        ],
        [
            "id-3", "2026-04-04T21:00:00+00:00", "2026-04-05",
            "3", "Caden Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
    ]
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    pending = store.list_pending(date(2026, 4, 12))
    assert len(pending) == 1
    assert pending[0].id == "id-1"


def test_append_confirmation():
    sheets = MagicMock()
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    pc = PendingConfirmation(
        id="new-1",
        sent_at=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
        pickup_date=date(2026, 4, 12),
        sheet_row_numbers=[3, 4],
        children_names=["Caden Shim", "Easton Shim"],
        ongoing_person="Hanseul or Deandra",
        parent_phones=["+15551110000"],
        parent_names=["Hanseul Shim"],
        status="pending",
    )
    store.append(pc)
    sheets.append_row.assert_called_once()
    args = sheets.append_row.call_args.args
    assert args[0] == "'Pending Confirmations'!A:L"
    assert args[1][0] == "new-1"


def test_find_pending_for_phone_returns_most_recent():
    sheets = MagicMock()
    sheets.read_range.return_value = [
        PendingConfirmation.SHEET_HEADERS,
        [
            "id-old", "2026-04-11T20:00:00+00:00", "2026-04-12",
            "3", "Caden Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
        [
            "id-new", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "4", "Easton Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
    ]
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    found = store.find_pending_for_phone("+15551110000", date(2026, 4, 12))
    assert found.id == "id-new"


def test_update_status_rewrites_row():
    sheets = MagicMock()
    sheets.read_range.return_value = [
        PendingConfirmation.SHEET_HEADERS,
        [
            "id-1", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "3", "Caden Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
    ]
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    store.mark_resolved(
        "id-1",
        status="confirmed",
        resolved_at=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
        reply_text="yes",
        resolved_value="",
    )
    sheets.update_range.assert_called_once()
    rng = sheets.update_range.call_args.args[0]
    assert "'Pending Confirmations'" in rng


def test_append_send_errors_writes_sentinel_row():
    sheets = MagicMock()
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    store.append_send_errors(date(2026, 4, 12), ["no phones for Ghost Kid", "twilio 500"])
    assert sheets.append_row.call_count == 1
    row = sheets.append_row.call_args.args[1]
    assert row[0] == "send-errors:2026-04-12"
    assert row[8] == "send_errors"
    assert "Ghost Kid" in row[10]


def test_get_send_errors_returns_lines():
    sheets = MagicMock()
    sheets.read_range.return_value = [
        PendingConfirmation.SHEET_HEADERS,
        [
            "send-errors:2026-04-12", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "", "", "", "", "", "send_errors", "",
            "no phones for Ghost Kid\ntwilio 500", "",
        ],
    ]
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    assert store.get_send_errors(date(2026, 4, 12)) == [
        "no phones for Ghost Kid",
        "twilio 500",
    ]
