from unittest.mock import MagicMock
from child_pickup.kids_info import load_kids_info, normalize_phone


def test_normalize_phone_adds_plus_and_country():
    assert normalize_phone("(555) 123-4567") == "+15551234567"
    assert normalize_phone("555-123-4567") == "+15551234567"
    assert normalize_phone("+15551234567") == "+15551234567"
    assert normalize_phone("15551234567") == "+15551234567"
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_load_kids_info_builds_lookup():
    headers = [
        "City", "Ministry Group", "Domain",
        "Name (First & Last)", "Gender", "Child's Bday",
        "Age (yrs)", "Mother", "Mother's phone #", "Father", "Father's phone #",
        "Allergy", "If allergy, describe", "Allergic Symptoms",
        "Preferred Course of Treatment", "Insurance",
    ]
    rows = [
        headers,
        ["DC", "MG1", "D1", "Estelle Chow", "F", "01/01/2018", "6",
         "Jenny Chow", "(555) 111-1111", "Alan Chow", "555-222-2222",
         "", "", "", "", ""],
        ["DC", "MG1", "D1", "Caden Shim", "M", "01/01/2018", "6",
         "Deandra Shim", "555-333-3333", "Hanseul Shim", "555-444-4444",
         "", "", "", "", ""],
    ]
    sheets = MagicMock()
    sheets.read_range.return_value = rows

    lookup = load_kids_info(sheets, tab_name="All DMV KidsInfo")
    assert lookup["Estelle Chow"].mother_name == "Jenny Chow"
    assert lookup["Estelle Chow"].mother_phone == "+15551111111"
    assert lookup["Estelle Chow"].father_phone == "+15552222222"
    assert lookup["Caden Shim"].father_name == "Hanseul Shim"
    assert lookup["Caden Shim"].mother_phone == "+15553333333"
