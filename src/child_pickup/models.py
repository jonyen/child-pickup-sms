# src/child_pickup/models.py
from dataclasses import dataclass


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
