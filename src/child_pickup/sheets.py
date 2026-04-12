from __future__ import annotations
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, service_account_info: dict, spreadsheet_id: str):
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        self.service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self.spreadsheet_id = spreadsheet_id

    def read_range(self, range_a1: str) -> list[list[str]]:
        resp = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_a1)
            .execute()
        )
        return resp.get("values", [])

    def update_range(self, range_a1: str, values: list[list]) -> None:
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_a1,
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

    def append_row(self, range_a1: str, row: list) -> None:
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=range_a1,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
