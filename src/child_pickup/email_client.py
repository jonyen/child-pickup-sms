from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import boto3

from .logging_setup import get_logger

log = get_logger(__name__)


@dataclass
class GroupOutcome:
    pickup_person: str
    children: list[str]
    original_ongoing: Optional[str] = None
    parent_contacts: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class SummaryData:
    pickup_date: date
    confirmed: list[GroupOutcome]
    changed: list[GroupOutcome]
    absent: list[GroupOutcome]
    no_response: list[GroupOutcome]
    send_errors: list[str]


class EmailClient:
    def __init__(
        self,
        sender: str,
        recipients: list[str],
        region: str,
        dry_run: bool = False,
    ):
        self.sender = sender
        self.recipients = recipients
        self.region = region
        self.dry_run = dry_run

    def send_summary(self, data: SummaryData) -> None:
        subject = f"Pickup summary {data.pickup_date.isoformat()}"
        body = self._format_body(data)
        if self.dry_run:
            log.info("dry_run_email", subject=subject, body=body)
            return
        ses = boto3.client("ses", region_name=self.region)
        ses.send_email(
            Source=self.sender,
            Destination={"ToAddresses": self.recipients},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )

    @staticmethod
    def _format_body(data: SummaryData) -> str:
        lines = [f"Pickup date: {data.pickup_date.isoformat()}", ""]

        lines.append(f"Confirmed ({len(data.confirmed)}):")
        if not data.confirmed:
            lines.append("  (none)")
        for g in data.confirmed:
            lines.append(f"  - {g.pickup_person}: {', '.join(g.children)}")
        lines.append("")

        lines.append(f"Changed ({len(data.changed)}):")
        if not data.changed:
            lines.append("  (none)")
        for g in data.changed:
            orig = f" (was: {g.original_ongoing})" if g.original_ongoing else ""
            lines.append(f"  - {g.pickup_person}{orig}: {', '.join(g.children)}")
        lines.append("")

        lines.append(f"Absent ({len(data.absent)}):")
        if not data.absent:
            lines.append("  (none)")
        for g in data.absent:
            lines.append(f"  - {', '.join(g.children)}")
        lines.append("")

        lines.append(f"No response ({len(data.no_response)}):")
        if not data.no_response:
            lines.append("  (none)")
        for g in data.no_response:
            lines.append(f"  - {g.pickup_person}: {', '.join(g.children)}")
            for name, phone in g.parent_contacts:
                lines.append(f"      contact: {name} {phone}")
        lines.append("")

        if data.send_errors:
            lines.append(f"Send errors ({len(data.send_errors)}):")
            for err in data.send_errors:
                lines.append(f"  - {err}")
            lines.append("")

        return "\n".join(lines)
