from unittest.mock import MagicMock
from child_pickup.sheets import SheetsClient


def _make_client_with_values(values):
    svc = MagicMock()
    svc.spreadsheets().values().get().execute.return_value = {"values": values}
    client = SheetsClient.__new__(SheetsClient)
    client.service = svc
    client.spreadsheet_id = "sid-123"
    return client, svc


def test_read_range_returns_values():
    client, _ = _make_client_with_values([["a", "b"], ["c", "d"]])
    rows = client.read_range("Sheet1!A1:B2")
    assert rows == [["a", "b"], ["c", "d"]]


def test_read_range_defaults_to_empty():
    svc = MagicMock()
    svc.spreadsheets().values().get().execute.return_value = {}
    client = SheetsClient.__new__(SheetsClient)
    client.service = svc
    client.spreadsheet_id = "sid-123"
    assert client.read_range("Sheet1!A1:B2") == []


def test_update_range_passes_params():
    svc = MagicMock()
    client = SheetsClient.__new__(SheetsClient)
    client.service = svc
    client.spreadsheet_id = "sid-123"
    client.update_range("Sheet1!D5", [["NEW"]])
    svc.spreadsheets().values().update.assert_called_with(
        spreadsheetId="sid-123",
        range="Sheet1!D5",
        valueInputOption="RAW",
        body={"values": [["NEW"]]},
    )


def test_append_row_passes_params():
    svc = MagicMock()
    client = SheetsClient.__new__(SheetsClient)
    client.service = svc
    client.spreadsheet_id = "sid-123"
    client.append_row("Sheet1", ["a", "b", "c"])
    svc.spreadsheets().values().append.assert_called_with(
        spreadsheetId="sid-123",
        range="Sheet1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [["a", "b", "c"]]},
    )
