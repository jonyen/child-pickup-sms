# tests/test_send.py
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from child_pickup.send import run_send_flow, SendResult
from child_pickup.models import Child, Group
from child_pickup.kids_info import KidInfo


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


def test_send_flow_skips_existing_pending_and_sends_new():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
        "'Pending Confirmations'!A:L": [],
    }[rng]

    twilio = MagicMock()
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pending_tab="Pending Confirmations",
        target_date=date(2026, 4, 12),
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
    )

    # Two groups: Shim (2 kids, 2 parents) and Lee (1 kid, 2 parents)
    assert result.groups_sent == 2
    assert twilio.send.call_count == 4  # 2 groups * 2 parents
    # Pending rows appended
    assert sheets.append_row.call_count == 2


def test_send_flow_skips_group_already_pending():
    pending_rows = [
        [
            "id-existing", "2026-04-11T20:00:00+00:00", "2026-04-12",
            "3,4", "Caden Shim,Easton Shim", "Hanseul or Deandra",
            "+15552221111", "Hanseul Shim", "pending", "", "", "",
        ],
    ]
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
        "'Pending Confirmations'!A:L": [
            __import__("child_pickup.models", fromlist=["PendingConfirmation"])
            .PendingConfirmation.SHEET_HEADERS
        ] + pending_rows,
    }[rng]

    twilio = MagicMock()
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pending_tab="Pending Confirmations",
        target_date=date(2026, 4, 12),
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
    )

    # Only the Lee group should have been sent
    assert result.groups_sent == 1
    assert sheets.append_row.call_count == 1


def test_send_flow_aborts_if_column_missing():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
        "'Pending Confirmations'!A:L": [],
    }[rng]
    twilio = MagicMock()
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pending_tab="Pending Confirmations",
        target_date=date(2026, 5, 3),  # not in headers
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 5, 2, 21, 0, tzinfo=timezone.utc),
    )
    assert result.aborted is True
    twilio.send.assert_not_called()
