# tests/test_models.py
from child_pickup.models import Child, Group, PendingConfirmation
from datetime import date, datetime, timezone


def test_child_defaults():
    c = Child(full_name="Estelle Chow", last_name="Chow", row_number=6, ongoing_person="Jenny or Alan")
    assert c.full_name == "Estelle Chow"
    assert c.row_number == 6
    assert c.ongoing_person == "Jenny or Alan"


def test_group_dedupes_phones():
    c1 = Child(full_name="Caden Shim", last_name="Shim", row_number=28, ongoing_person="Hanseul or Deandra")
    c2 = Child(full_name="Easton Shim", last_name="Shim", row_number=29, ongoing_person="Hanseul or Deandra")
    g = Group(
        ongoing_person="Hanseul or Deandra",
        children=[c1, c2],
        parent_phones=["+15551110000", "+15552220000", "+15551110000"],
        parent_names=["Hanseul Shim", "Deandra Shim", "Hanseul Shim"],
    )
    assert g.unique_phones() == ["+15551110000", "+15552220000"]


def test_pending_confirmation_roundtrip():
    pc = PendingConfirmation(
        id="abc-123",
        sent_at=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
        pickup_date=date(2026, 4, 12),
        sheet_row_numbers=[28, 29, 30],
        children_names=["Caden Shim", "Easton Shim", "Mason Shim"],
        ongoing_person="Hanseul or Deandra",
        parent_phones=["+15551110000", "+15552220000"],
        parent_names=["Hanseul Shim", "Deandra Shim"],
        status="pending",
        resolved_at=None,
        reply_text=None,
        resolved_value=None,
    )
    row = pc.to_sheet_row()
    assert row[0] == "abc-123"
    assert "28,29,30" in row
    parsed = PendingConfirmation.from_sheet_row(row)
    assert parsed.id == pc.id
    assert parsed.sheet_row_numbers == [28, 29, 30]
    assert parsed.status == "pending"
