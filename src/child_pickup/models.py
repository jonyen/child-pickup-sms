# src/child_pickup/models.py
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Child:
    full_name: str
    last_name: str
    row_number: int  # 1-indexed row in Pickup Schedule sheet
    ongoing_person: str


@dataclass
class Group:
    ongoing_person: str
    children: list[Child]
    parent_phones: list[str]
    parent_names: list[str]

    def unique_phones(self) -> list[str]:
        seen = set()
        out = []
        for p in self.parent_phones:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    def child_names(self) -> list[str]:
        return [c.full_name for c in self.children]

    def row_numbers(self) -> list[int]:
        return [c.row_number for c in self.children]


@dataclass
class PendingConfirmation:
    id: str
    sent_at: datetime
    pickup_date: date
    sheet_row_numbers: list[int]
    children_names: list[str]
    ongoing_person: str
    parent_phones: list[str]
    parent_names: list[str]
    status: str  # pending | confirmed | changed | no_response
    resolved_at: Optional[datetime] = None
    reply_text: Optional[str] = None
    resolved_value: Optional[str] = None

    SHEET_HEADERS = [
        "id",
        "sent_at",
        "pickup_date",
        "sheet_row_numbers",
        "children_names",
        "ongoing_person",
        "parent_phones",
        "parent_names",
        "status",
        "resolved_at",
        "reply_text",
        "resolved_value",
    ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.id,
            self.sent_at.isoformat(),
            self.pickup_date.isoformat(),
            ",".join(str(n) for n in self.sheet_row_numbers),
            ",".join(self.children_names),
            self.ongoing_person,
            ",".join(self.parent_phones),
            ",".join(self.parent_names),
            self.status,
            self.resolved_at.isoformat() if self.resolved_at else "",
            self.reply_text or "",
            self.resolved_value or "",
        ]

    @classmethod
    def from_sheet_row(cls, row: list[str]) -> "PendingConfirmation":
        # Tolerate short rows by padding
        padded = list(row) + [""] * (len(cls.SHEET_HEADERS) - len(row))
        return cls(
            id=padded[0],
            sent_at=datetime.fromisoformat(padded[1]),
            pickup_date=date.fromisoformat(padded[2]),
            sheet_row_numbers=[int(n) for n in padded[3].split(",") if n],
            children_names=[n for n in padded[4].split(",") if n],
            ongoing_person=padded[5],
            parent_phones=[p for p in padded[6].split(",") if p],
            parent_names=[n for n in padded[7].split(",") if n],
            status=padded[8],
            resolved_at=datetime.fromisoformat(padded[9]) if padded[9] else None,
            reply_text=padded[10] or None,
            resolved_value=padded[11] or None,
        )
