# src/child_pickup/send.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime

from .kids_info import load_kids_info
from .logging_setup import get_logger
from .pickup_schedule import (
    ensure_next_week_column,
    find_date_column_index,
    group_blank_rows,
    read_blank_rows,
)
from .twilio_client import TwilioClient, compose_sms_body

log = get_logger(__name__)


@dataclass
class SendResult:
    groups_sent: int = 0
    sms_sent: int = 0
    sms_failed: int = 0
    send_errors: list[str] = field(default_factory=list)
    aborted: bool = False


def run_send_flow(
    *,
    sheets,
    twilio: TwilioClient,
    pickup_tab: str,
    kids_info_tab: str,
    target_date: date,
    coordinator_name: str,
    now: datetime,
) -> SendResult:
    result = SendResult()

    pickup_rows = sheets.read_range(f"'{pickup_tab}'!A1:Z1000")
    if not pickup_rows:
        log.error("send_flow_empty_pickup_sheet")
        result.aborted = True
        return result
    headers = pickup_rows[0]
    col_index = find_date_column_index(headers, target_date)
    if col_index is None:
        log.error("send_flow_column_not_found", target=target_date.isoformat())
        result.aborted = True
        return result

    ensure_next_week_column(sheets, pickup_tab, headers, target_date)

    kids_info = load_kids_info(sheets, kids_info_tab)
    blank_children = read_blank_rows(pickup_rows, col_index)

    for c in blank_children:
        if c.full_name not in kids_info:
            result.send_errors.append(f"no KidsInfo entry for {c.full_name}")

    groups = group_blank_rows(blank_children, kids_info)

    in_groups = {c.full_name for g in groups for c in g.children}
    for c in blank_children:
        if c.full_name not in in_groups and c.full_name in kids_info:
            result.send_errors.append(f"no parent phones for {c.full_name}")

    pickup_md = f"{target_date.month}/{target_date.day}"

    for group in groups:
        body = compose_sms_body(group, pickup_md=pickup_md, coordinator=coordinator_name)
        for phone in group.unique_phones():
            try:
                twilio.send(to=phone, body=body)
                result.sms_sent += 1
            except Exception as e:
                log.warning("sms_send_failed", to=phone, error=str(e))
                try:
                    twilio.send(to=phone, body=body)  # retry once
                    result.sms_sent += 1
                except Exception as e2:
                    result.sms_failed += 1
                    result.send_errors.append(f"SMS send failed to {phone}: {e2}")

        result.groups_sent += 1
        log.info(
            "send_flow_group_sent",
            ongoing=group.ongoing_person,
            children=group.child_names(),
            phones=group.unique_phones(),
        )

    if result.send_errors:
        log.warning("send_flow_errors", errors=result.send_errors)

    return result
