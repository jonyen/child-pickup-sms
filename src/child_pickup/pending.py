# src/child_pickup/pending.py
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Optional

from .models import PendingConfirmation


class PendingStore:
    def __init__(self, sheets_client, tab_name: str):
        self.sheets = sheets_client
        self.tab_name = tab_name
        self._range_all = f"'{tab_name}'!A:L"

    def _read_all(self) -> list[tuple[int, PendingConfirmation]]:
        """Return (row_number, PendingConfirmation) pairs. Row 1 is header."""
        rows = self.sheets.read_range(self._range_all)
        out = []
        for i, r in enumerate(rows[1:], start=2):
            if not r or not r[0]:
                continue
            out.append((i, PendingConfirmation.from_sheet_row(r)))
        return out

    def list_pending(self, pickup_date: date) -> list[PendingConfirmation]:
        return [
            pc
            for _, pc in self._read_all()
            if pc.status == "pending" and pc.pickup_date == pickup_date
        ]

    def append(self, pc: PendingConfirmation) -> None:
        self.sheets.append_row(self._range_all, pc.to_sheet_row())

    def find_pending_for_phone(
        self, phone: str, pickup_date: date
    ) -> Optional[PendingConfirmation]:
        candidates = [
            pc
            for _, pc in self._read_all()
            if pc.status == "pending"
            and pc.pickup_date == pickup_date
            and phone in pc.parent_phones
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda pc: pc.sent_at)

    def mark_resolved(
        self,
        pending_id: str,
        *,
        status: str,
        resolved_at: datetime,
        reply_text: Optional[str],
        resolved_value: Optional[str],
    ) -> None:
        all_rows = self._read_all()
        for row_number, pc in all_rows:
            if pc.id != pending_id:
                continue
            pc.status = status
            pc.resolved_at = resolved_at
            pc.reply_text = reply_text
            pc.resolved_value = resolved_value
            rng = f"'{self.tab_name}'!A{row_number}:L{row_number}"
            self.sheets.update_range(rng, [pc.to_sheet_row()])
            return
        raise KeyError(f"pending id not found: {pending_id}")

    def group_already_sent(
        self, pickup_date: date, sheet_row_numbers: list[int]
    ) -> bool:
        target = sorted(sheet_row_numbers)
        for _, pc in self._read_all():
            if pc.pickup_date == pickup_date and sorted(pc.sheet_row_numbers) == target:
                return True
        return False

    def append_send_errors(self, pickup_date: date, errors: list[str]) -> None:
        """Persist send-time errors as a sentinel row so the cutoff flow can include them."""
        if not errors:
            return
        sentinel = PendingConfirmation(
            id=f"send-errors:{pickup_date.isoformat()}",
            sent_at=datetime.now(tz=timezone.utc),
            pickup_date=pickup_date,
            sheet_row_numbers=[],
            children_names=[],
            ongoing_person="",
            parent_phones=[],
            parent_names=[],
            status="send_errors",
            resolved_at=None,
            reply_text="\n".join(errors),
            resolved_value=None,
        )
        self.sheets.append_row(self._range_all, sentinel.to_sheet_row())

    def get_send_errors(self, pickup_date: date) -> list[str]:
        sentinel_id = f"send-errors:{pickup_date.isoformat()}"
        for _, pc in self._read_all():
            if pc.id == sentinel_id and pc.status == "send_errors":
                return [line for line in (pc.reply_text or "").splitlines() if line]
        return []
