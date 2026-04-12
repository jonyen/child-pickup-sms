from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from .logging_setup import get_logger
from .parser import ReplyParser, ParseResult
from .pending import PendingStore

log = get_logger(__name__)


@dataclass
class ReplyOutcome:
    action: str  # confirm | change | ambiguous | unmatched
    reply_text: Optional[str] = None  # TwiML body text if non-empty


def _col_letter(index_zero_based: int) -> str:
    # Single-letter A..Z is sufficient for this sheet
    return chr(ord("A") + index_zero_based)


def handle_reply(
    *,
    sheets,
    store: PendingStore,
    parser: ReplyParser,
    from_phone: str,
    body: str,
    pickup_tab: str,
    pickup_col_index: int,
    pickup_date: date,
    now: datetime,
) -> ReplyOutcome:
    pending = store.find_pending_for_phone(from_phone, pickup_date)
    if not pending:
        return ReplyOutcome(
            action="unmatched",
            reply_text="Thanks, but we don't have a pending pickup confirmation for this number right now.",
        )

    result: ParseResult = parser.parse(
        body,
        ongoing_person=pending.ongoing_person,
        children_names=pending.children_names,
    )

    col_letter = _col_letter(pickup_col_index)

    if result.action == "confirm":
        _write_cells(sheets, pickup_tab, col_letter, pending.sheet_row_numbers, "")
        store.mark_resolved(
            pending.id,
            status="confirmed",
            resolved_at=now,
            reply_text=body,
            resolved_value="",
        )
        return ReplyOutcome(action="confirm")

    if result.action == "change":
        new_name = result.new_pickup_person or ""
        _write_cells(sheets, pickup_tab, col_letter, pending.sheet_row_numbers, new_name)
        store.mark_resolved(
            pending.id,
            status="changed",
            resolved_at=now,
            reply_text=body,
            resolved_value=new_name,
        )
        return ReplyOutcome(action="change")

    # ambiguous — leave pending
    return ReplyOutcome(
        action="ambiguous",
        reply_text=(
            f"Sorry, didn't catch that — could you reply YES to confirm "
            f"{pending.ongoing_person}, or just the name of who's picking up?"
        ),
    )


def _write_cells(sheets, tab: str, col_letter: str, rows: list[int], value: str) -> None:
    for r in rows:
        sheets.update_range(f"'{tab}'!{col_letter}{r}", [[value]])
