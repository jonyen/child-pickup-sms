# tests/test_models.py
from child_pickup.models import Child, Group


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
