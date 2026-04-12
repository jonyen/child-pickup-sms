from __future__ import annotations
from datetime import date, datetime

from .email_client import EmailClient, GroupOutcome, SummaryData
from .kids_info import KidInfo, load_kids_info
from .logging_setup import get_logger
from .pickup_schedule import read_blank_rows, read_filled_rows

log = get_logger(__name__)


def _col_letter(index_zero_based: int) -> str:
    return chr(ord("A") + index_zero_based)


def run_cutoff_flow(
    *,
    sheets,
    email: EmailClient,
    pickup_tab: str,
    kids_info_tab: str,
    pickup_col_index: int,
    target_date: date,
    now: datetime,
) -> None:
    pickup_rows = sheets.read_range(f"'{pickup_tab}'!A1:Z1000")
    if not pickup_rows:
        log.error("cutoff_empty_pickup_sheet")
        return

    kids_info = load_kids_info(sheets, kids_info_tab)
    col_letter = _col_letter(pickup_col_index)

    blank_children = read_blank_rows(pickup_rows, pickup_col_index)
    for child in blank_children:
        sheets.update_range(
            f"'{pickup_tab}'!{col_letter}{child.row_number}", [["NO RESPONSE"]]
        )
        log.info("cutoff_no_response", child=child.full_name, row=child.row_number)

    filled_rows = read_filled_rows(pickup_rows, pickup_col_index)
    summary = _build_summary(
        blank_children=blank_children,
        filled_rows=filled_rows,
        kids_info=kids_info,
        target_date=target_date,
    )
    email.send_summary(summary)


def _build_summary(
    *,
    blank_children,
    filled_rows,
    kids_info: dict[str, KidInfo],
    target_date: date,
) -> SummaryData:
    confirmed: list[GroupOutcome] = []
    changed: list[GroupOutcome] = []
    absent: list[GroupOutcome] = []
    no_response: list[GroupOutcome] = []

    for child, cell_value in filled_rows:
        if cell_value == child.ongoing_person:
            confirmed.append(
                GroupOutcome(
                    pickup_person=child.ongoing_person,
                    children=[child.full_name],
                )
            )
        elif cell_value == "ABSENT":
            absent.append(
                GroupOutcome(
                    pickup_person=child.ongoing_person,
                    children=[child.full_name],
                )
            )
        else:
            changed.append(
                GroupOutcome(
                    pickup_person=cell_value,
                    children=[child.full_name],
                    original_ongoing=child.ongoing_person,
                )
            )

    for child in blank_children:
        info = kids_info.get(child.full_name)
        contacts: list[tuple[str, str]] = []
        if info:
            for phone, name in (
                (info.mother_phone, info.mother_name),
                (info.father_phone, info.father_name),
            ):
                if phone:
                    contacts.append((name or "", phone))
        no_response.append(
            GroupOutcome(
                pickup_person=child.ongoing_person,
                children=[child.full_name],
                parent_contacts=contacts,
            )
        )

    return SummaryData(
        pickup_date=target_date,
        confirmed=confirmed,
        changed=changed,
        absent=absent,
        no_response=no_response,
        send_errors=[],
    )
