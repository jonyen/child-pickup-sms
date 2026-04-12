from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from .kids_info import KidInfo, load_kids_info
from .logging_setup import get_logger
from .parser import ReplyParser, ParseResult
from .pickup_schedule import find_children_for_phone, read_blank_rows

log = get_logger(__name__)


@dataclass
class ReplyOutcome:
    action: str  # confirm | change | absent | ambiguous | unmatched
    reply_text: Optional[str] = None  # TwiML body text if non-empty
    notify_phones: list[str] = None  # other parent phones to inform
    notify_text: Optional[str] = None  # SMS body for those phones

    def __post_init__(self):
        if self.notify_phones is None:
            self.notify_phones = []


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

    other_phones = _other_parent_phones(matching, kids_info, from_phone)
    kids_phrase = _format_children_names(children_names)

    if result.action == "confirm":
        _write_cells(sheets, pickup_tab, col_letter, rows, ongoing_person)
        log.info("reply_confirmed", children=children_names, ongoing=ongoing_person)
        notify_text = (
            f"FYI — {ongoing_person} picking up {kids_phrase} has been confirmed. "
            f"No need to reply."
        ) if other_phones else None
        return ReplyOutcome(
            action="confirm", notify_phones=other_phones, notify_text=notify_text,
        )

    if result.action == "change":
        new_name = result.new_pickup_person or ""
        _write_cells(sheets, pickup_tab, col_letter, rows, new_name)
        log.info("reply_changed", children=children_names, new_person=new_name)
        notify_text = (
            f"FYI — pickup for {kids_phrase} has been changed to {new_name}. "
            f"No need to reply."
        ) if other_phones else None
        return ReplyOutcome(
            action="change", notify_phones=other_phones, notify_text=notify_text,
        )

    if result.action == "absent":
        _write_cells(sheets, pickup_tab, col_letter, rows, "ABSENT")
        log.info("reply_absent", children=children_names)
        notify_text = (
            f"FYI — {kids_phrase} marked as not coming. No need to reply."
        ) if other_phones else None
        return ReplyOutcome(
            action="absent", notify_phones=other_phones, notify_text=notify_text,
        )

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


def _other_parent_phones(
    matching_children, kids_info: dict[str, KidInfo], from_phone: str,
) -> list[str]:
    phones: set[str] = set()
    for child in matching_children:
        info = kids_info.get(child.full_name)
        if not info:
            continue
        for phone in (info.mother_phone, info.father_phone):
            if phone and phone != from_phone:
                phones.add(phone)
    return sorted(phones)


def _format_children_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"
