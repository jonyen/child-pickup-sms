from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from .email_client import EmailClient, GroupOutcome, SummaryData
from .logging_setup import get_logger
from .models import PendingConfirmation
from .pending import PendingStore

log = get_logger(__name__)


def _col_letter(index_zero_based: int) -> str:
    return chr(ord("A") + index_zero_based)


def run_cutoff_flow(
    *,
    sheets,
    store: PendingStore,
    email: EmailClient,
    pickup_tab: str,
    pickup_col_index: int,
    target_date: date,
    now: datetime,
) -> None:
    pending = store.list_pending(target_date)
    col_letter = _col_letter(pickup_col_index)

    for pc in pending:
        for row in pc.sheet_row_numbers:
            sheets.update_range(f"'{pickup_tab}'!{col_letter}{row}", [["NO RESPONSE"]])
        store.mark_resolved(
            pc.id,
            status="no_response",
            resolved_at=now,
            reply_text=None,
            resolved_value="NO RESPONSE",
        )
        log.info("cutoff_no_response", pending_id=pc.id, children=pc.children_names)

    send_errors = store.get_send_errors(target_date)
    summary = _build_summary(store, target_date, send_errors)
    email.send_summary(summary)


def _build_summary(
    store: PendingStore, target_date: date, send_errors: list[str]
) -> SummaryData:
    confirmed: list[GroupOutcome] = []
    changed: list[GroupOutcome] = []
    no_response: list[GroupOutcome] = []

    for _, pc in store._read_all():
        if pc.pickup_date != target_date:
            continue
        if pc.status == "confirmed":
            confirmed.append(
                GroupOutcome(
                    pickup_person=pc.ongoing_person,
                    children=pc.children_names,
                )
            )
        elif pc.status == "changed":
            changed.append(
                GroupOutcome(
                    pickup_person=pc.resolved_value or "",
                    children=pc.children_names,
                    original_ongoing=pc.ongoing_person,
                )
            )
        elif pc.status == "no_response":
            contacts = list(zip(pc.parent_names, pc.parent_phones))
            no_response.append(
                GroupOutcome(
                    pickup_person=pc.ongoing_person,
                    children=pc.children_names,
                    parent_contacts=contacts,
                )
            )

    return SummaryData(
        pickup_date=target_date,
        confirmed=confirmed,
        changed=changed,
        no_response=no_response,
        send_errors=send_errors,
    )
