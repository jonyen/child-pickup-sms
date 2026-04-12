from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from .kids_info import load_kids_info
from .logging_setup import get_logger
from .parser import ReplyParser, ParseResult
from .pickup_schedule import find_children_for_phone, read_blank_rows

log = get_logger(__name__)


@dataclass
class ReplyOutcome:
    action: str  # confirm | change | ambiguous | unmatched
    reply_text: Optional[str] = None  # TwiML body text if non-empty


def _col_letter(index_zero_based: int) -> str:
    return chr(ord("A") + index_zero_based)


def handle_reply(
    *,
    sheets,
    parser: ReplyParser,
    from_phone: str,
    body: str,
    pickup_tab: str,
    kids_info_tab: str,
    pickup_col_index: int,
    pickup_date: date,
    now: datetime,
) -> ReplyOutcome:
    pickup_rows = sheets.read_range(f"'{pickup_tab}'!A1:Z1000")
    if not pickup_rows:
        return ReplyOutcome(
            action="unmatched",
            reply_text="Thanks, but we don't have a pending pickup confirmation for this number right now.",
        )

    kids_info = load_kids_info(sheets, kids_info_tab)
    blank_children = read_blank_rows(pickup_rows, pickup_col_index)
    matching = find_children_for_phone(blank_children, kids_info, from_phone)

    if not matching:
        return ReplyOutcome(
            action="unmatched",
            reply_text="Thanks, but we don't have a pending pickup confirmation for this number right now.",
        )

    ongoing_person = matching[0].ongoing_person
    children_names = [c.full_name for c in matching]

    result: ParseResult = parser.parse(
        body,
        ongoing_person=ongoing_person,
        children_names=children_names,
    )

    col_letter = _col_letter(pickup_col_index)
    rows = [c.row_number for c in matching]

    if result.action == "confirm":
        _write_cells(sheets, pickup_tab, col_letter, rows, ongoing_person)
        log.info("reply_confirmed", children=children_names, ongoing=ongoing_person)
        return ReplyOutcome(action="confirm")

    if result.action == "change":
        new_name = result.new_pickup_person or ""
        _write_cells(sheets, pickup_tab, col_letter, rows, new_name)
        log.info("reply_changed", children=children_names, new_person=new_name)
        return ReplyOutcome(action="change")

    # ambiguous — leave row blank
    return ReplyOutcome(
        action="ambiguous",
        reply_text=(
            f"Sorry, didn't catch that — could you reply YES to confirm "
            f"{ongoing_person}, or just the name of who's picking up?"
        ),
    )


def _write_cells(sheets, tab: str, col_letter: str, rows: list[int], value: str) -> None:
    for r in rows:
        sheets.update_range(f"'{tab}'!{col_letter}{r}", [[value]])
