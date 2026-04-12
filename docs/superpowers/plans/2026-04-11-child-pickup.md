# Child Pickup Confirmation App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AWS Lambda app that every Saturday 5pm ET reads a Google Sheets pickup schedule, texts parents via Twilio to confirm who's picking up their child on Sunday, parses replies, writes results back to the sheet, and emails a cutoff summary at 9pm ET.

**Architecture:** Single Python 3.12 Lambda behind API Gateway + two EventBridge schedules. Handler dispatches on event shape into `send`, `reply`, or `cutoff` flow modules. Google Sheets serves as both source of truth (Pickup Schedule, All DMV KidsInfo) and pending-state storage (new Pending Confirmations tab). Twilio for SMS, SES for email, Secrets Manager for credentials, Claude Haiku for free-form reply parsing fallback. SAM for infrastructure-as-code.

**Tech Stack:** Python 3.12, AWS Lambda + API Gateway + EventBridge + SES + Secrets Manager + CloudWatch, AWS SAM, Google Sheets API (`google-api-python-client`, `google-auth`), Twilio Python SDK, Anthropic Python SDK, pytest + pytest-mock, structlog.

---

## Design Principles

- **TDD:** write the failing test first for every module. Implementation is minimal — only what the test demands.
- **One responsibility per module.** Files are small and focused.
- **Boundary classes are mockable.** `SheetsClient`, `TwilioClient`, `ClaudeParser`, `EmailClient` are narrow interfaces so tests mock them without touching real APIs.
- **Flow modules are thin.** `send.py`, `reply.py`, `cutoff.py` orchestrate boundary clients. No business logic buried in I/O code.
- **Configuration is centralized.** `config.py` resolves env vars and fetches Secrets Manager values once at cold start.
- **`DRY_RUN` is real.** Every side-effecting boundary client honors it by logging intended actions instead of executing.

---

## File Structure

```
child-pickup/
├── pyproject.toml
├── template.yaml                 # SAM template
├── .gitignore
├── README.md
├── src/
│   └── child_pickup/
│       ├── __init__.py
│       ├── handler.py            # Lambda entrypoint; dispatches by event shape
│       ├── config.py             # Env vars + Secrets Manager fetch (cached)
│       ├── logging_setup.py      # Structured JSON logging
│       ├── models.py             # Dataclasses: Child, PendingConfirmation, Group
│       ├── sheets.py             # SheetsClient (low-level Google Sheets wrapper)
│       ├── kids_info.py          # Parse All DMV KidsInfo tab
│       ├── pickup_schedule.py    # Read pickup schedule, find blanks, group
│       ├── pending.py            # Read/write Pending Confirmations tab
│       ├── twilio_client.py      # TwilioClient: send, verify signature, compose
│       ├── parser.py             # ReplyParser: regex + Claude Haiku fallback
│       ├── email_client.py       # EmailClient: SES summary email
│       ├── send.py               # Send flow orchestration
│       ├── reply.py              # Reply flow orchestration
│       └── cutoff.py             # Cutoff flow orchestration
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_kids_info.py
    ├── test_pickup_schedule.py
    ├── test_pending.py
    ├── test_twilio_client.py
    ├── test_parser.py
    ├── test_email_client.py
    ├── test_send.py
    ├── test_reply.py
    ├── test_cutoff.py
    └── test_handler.py
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/child_pickup/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `README.md`

**This task is scaffolding — no TDD.**

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "child-pickup"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "google-api-python-client==2.149.0",
    "google-auth==2.35.0",
    "twilio==9.3.5",
    "anthropic==0.39.0",
    "boto3==1.35.55",
    "structlog==24.4.0",
    "pydantic==2.9.2",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.3",
    "pytest-mock==3.14.0",
    "freezegun==1.5.1",
    "moto[ses,secretsmanager]==5.0.20",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.aws-sam/
dist/
build/
*.egg-info/
.env
.env.*
```

- [ ] **Step 3: Create empty package files**

```python
# src/child_pickup/__init__.py
```

```python
# tests/__init__.py
```

- [ ] **Step 4: Create `tests/conftest.py` with shared fixtures**

```python
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_sheets_client():
    return MagicMock()


@pytest.fixture
def mock_twilio_client():
    return MagicMock()


@pytest.fixture
def mock_claude_client():
    return MagicMock()


@pytest.fixture
def mock_email_client():
    return MagicMock()
```

- [ ] **Step 5: Create minimal `README.md`**

```markdown
# Child Pickup Confirmation App

Automated Saturday-night SMS confirmation workflow for Sunday child pickups, backed by Google Sheets.

See `docs/superpowers/specs/2026-04-11-child-pickup-design.md` for the full design.

## Develop

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Deploy

Requires AWS SAM CLI.

```
sam build
sam deploy --guided
```
```

- [ ] **Step 6: Install and verify**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```
Expected: `no tests ran` (or 0 collected) — exits 5, that's fine.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore src/child_pickup/__init__.py tests/__init__.py tests/conftest.py README.md
git commit -m "chore: scaffold child-pickup package"
```

---

## Task 2: Models

**Files:**
- Create: `src/child_pickup/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_models.py
from child_pickup.models import Child, Group, PendingConfirmation
from datetime import date, datetime, timezone


def test_child_defaults():
    c = Child(full_name="Estelle Chow", last_name="Chow", row_number=6, ongoing_person="Jenny or Alan")
    assert c.full_name == "Estelle Chow"
    assert c.row_number == 6
    assert c.ongoing_person == "Jenny or Alan"


def test_group_dedupes_phones():
    c1 = Child(full_name="Caden Shim", last_name="Shim", row_number=28, ongoing_person="Hanseul or Deandra")
    c2 = Child(full_name="Easton Shim", last_name="Shim", row_number=29, ongoing_person="Hanseul or Deandra")
    g = Group(
        ongoing_person="Hanseul or Deandra",
        children=[c1, c2],
        parent_phones=["+15551110000", "+15552220000", "+15551110000"],
        parent_names=["Hanseul Shim", "Deandra Shim", "Hanseul Shim"],
    )
    assert g.unique_phones() == ["+15551110000", "+15552220000"]


def test_pending_confirmation_roundtrip():
    pc = PendingConfirmation(
        id="abc-123",
        sent_at=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
        pickup_date=date(2026, 4, 12),
        sheet_row_numbers=[28, 29, 30],
        children_names=["Caden Shim", "Easton Shim", "Mason Shim"],
        ongoing_person="Hanseul or Deandra",
        parent_phones=["+15551110000", "+15552220000"],
        parent_names=["Hanseul Shim", "Deandra Shim"],
        status="pending",
        resolved_at=None,
        reply_text=None,
        resolved_value=None,
    )
    row = pc.to_sheet_row()
    assert row[0] == "abc-123"
    assert "28,29,30" in row
    parsed = PendingConfirmation.from_sheet_row(row)
    assert parsed.id == pc.id
    assert parsed.sheet_row_numbers == [28, 29, 30]
    assert parsed.status == "pending"
```

- [ ] **Step 2: Run test, verify failure**

```bash
pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'child_pickup.models'`

- [ ] **Step 3: Implement `models.py`**

```python
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_models.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/models.py tests/test_models.py
git commit -m "feat(models): add Child, Group, PendingConfirmation dataclasses"
```

---

## Task 3: Config and secrets loading

**Files:**
- Create: `src/child_pickup/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
import json
import os
import pytest
from unittest.mock import MagicMock, patch
from child_pickup.config import Config, get_config


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("SPREADSHEET_ID", "sid-123")
    monkeypatch.setenv("PICKUP_TAB_NAME", "Pickup Schedule")
    monkeypatch.setenv("KIDS_INFO_TAB_NAME", "All DMV KidsInfo")
    monkeypatch.setenv("PENDING_TAB_NAME", "Pending Confirmations")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550000000")
    monkeypatch.setenv("SUMMARY_EMAIL_RECIPIENTS", "a@b.com,c@d.com")
    monkeypatch.setenv("SUMMARY_EMAIL_FROM", "pickup@dmv.org")
    monkeypatch.setenv("COORDINATOR_NAME", "DMV pickup coordinator")
    monkeypatch.setenv("TIMEZONE", "America/New_York")
    monkeypatch.setenv("DRY_RUN", "false")

    cfg = Config.from_env()
    assert cfg.spreadsheet_id == "sid-123"
    assert cfg.summary_email_recipients == ["a@b.com", "c@d.com"]
    assert cfg.dry_run is False


def test_dry_run_true(monkeypatch):
    for k, v in _required_env().items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("DRY_RUN", "true")
    cfg = Config.from_env()
    assert cfg.dry_run is True


def test_missing_required_env(monkeypatch):
    monkeypatch.delenv("SPREADSHEET_ID", raising=False)
    for k, v in _required_env().items():
        if k != "SPREADSHEET_ID":
            monkeypatch.setenv(k, v)
    with pytest.raises(KeyError, match="SPREADSHEET_ID"):
        Config.from_env()


@patch("child_pickup.config.boto3")
def test_fetch_secrets(mock_boto3, monkeypatch):
    for k, v in _required_env().items():
        monkeypatch.setenv(k, v)
    cfg = Config.from_env()
    mock_sm = MagicMock()
    mock_boto3.client.return_value = mock_sm
    mock_sm.get_secret_value.side_effect = [
        {"SecretString": json.dumps({"account_sid": "AC1", "auth_token": "TOK"})},
        {"SecretString": json.dumps({"type": "service_account", "client_email": "svc@proj.iam"})},
        {"SecretString": json.dumps({"api_key": "sk-ant-1"})},
    ]
    secrets = cfg.load_secrets()
    assert secrets.twilio_account_sid == "AC1"
    assert secrets.twilio_auth_token == "TOK"
    assert secrets.google_service_account["client_email"] == "svc@proj.iam"
    assert secrets.anthropic_api_key == "sk-ant-1"


def _required_env() -> dict:
    return {
        "SPREADSHEET_ID": "sid-123",
        "PICKUP_TAB_NAME": "Pickup Schedule",
        "KIDS_INFO_TAB_NAME": "All DMV KidsInfo",
        "PENDING_TAB_NAME": "Pending Confirmations",
        "TWILIO_FROM_NUMBER": "+15550000000",
        "SUMMARY_EMAIL_RECIPIENTS": "a@b.com",
        "SUMMARY_EMAIL_FROM": "pickup@dmv.org",
        "COORDINATOR_NAME": "DMV pickup coordinator",
        "TIMEZONE": "America/New_York",
    }
```

- [ ] **Step 2: Run test, verify failure**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `config.py`**

```python
# src/child_pickup/config.py
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

import boto3


@dataclass
class Secrets:
    twilio_account_sid: str
    twilio_auth_token: str
    google_service_account: dict
    anthropic_api_key: str


@dataclass
class Config:
    spreadsheet_id: str
    pickup_tab_name: str
    kids_info_tab_name: str
    pending_tab_name: str
    twilio_from_number: str
    summary_email_recipients: list[str]
    summary_email_from: str
    coordinator_name: str
    timezone: str
    dry_run: bool
    aws_region: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            spreadsheet_id=os.environ["SPREADSHEET_ID"],
            pickup_tab_name=os.environ["PICKUP_TAB_NAME"],
            kids_info_tab_name=os.environ["KIDS_INFO_TAB_NAME"],
            pending_tab_name=os.environ["PENDING_TAB_NAME"],
            twilio_from_number=os.environ["TWILIO_FROM_NUMBER"],
            summary_email_recipients=[
                e.strip() for e in os.environ["SUMMARY_EMAIL_RECIPIENTS"].split(",") if e.strip()
            ],
            summary_email_from=os.environ["SUMMARY_EMAIL_FROM"],
            coordinator_name=os.environ["COORDINATOR_NAME"],
            timezone=os.environ["TIMEZONE"],
            dry_run=os.environ.get("DRY_RUN", "false").lower() == "true",
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        )

    def load_secrets(self) -> Secrets:
        sm = boto3.client("secretsmanager", region_name=self.aws_region)
        twilio = json.loads(sm.get_secret_value(SecretId="child-pickup/twilio")["SecretString"])
        google = json.loads(
            sm.get_secret_value(SecretId="child-pickup/google-service-account")["SecretString"]
        )
        anthropic = json.loads(
            sm.get_secret_value(SecretId="child-pickup/anthropic")["SecretString"]
        )
        return Secrets(
            twilio_account_sid=twilio["account_sid"],
            twilio_auth_token=twilio["auth_token"],
            google_service_account=google,
            anthropic_api_key=anthropic["api_key"],
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config.from_env()
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_config.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/config.py tests/test_config.py
git commit -m "feat(config): env + Secrets Manager loader"
```

---

## Task 4: Logging setup

**Files:**
- Create: `src/child_pickup/logging_setup.py`
- Create: `tests/test_logging_setup.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_logging_setup.py
import json
import logging
from child_pickup.logging_setup import configure_logging, get_logger


def test_logger_emits_json(capsys):
    configure_logging(level="INFO")
    log = get_logger("test")
    log.info("hello", pending_id="abc", pickup_date="2026-04-12")
    captured = capsys.readouterr().out.strip()
    # structlog JSONRenderer emits one JSON object per line
    payload = json.loads(captured.splitlines()[-1])
    assert payload["event"] == "hello"
    assert payload["pending_id"] == "abc"
    assert payload["pickup_date"] == "2026-04-12"
```

- [ ] **Step 2: Run test, verify failure**

```bash
pytest tests/test_logging_setup.py -v
```

- [ ] **Step 3: Implement `logging_setup.py`**

```python
# src/child_pickup/logging_setup.py
import logging
import sys
import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/logging_setup.py tests/test_logging_setup.py
git commit -m "feat(logging): structured JSON logging setup"
```

---

## Task 5: SheetsClient wrapper

**Files:**
- Create: `src/child_pickup/sheets.py`
- Create: `tests/test_sheets.py`

`SheetsClient` is a thin wrapper around the Google Sheets API. It exposes narrow methods (`read_range`, `update_range`, `append_row`, `find_row_index`). Tests mock the underlying `sheets_service` object, not the HTTP layer.

- [ ] **Step 1: Write failing test**

```python
# tests/test_sheets.py
from unittest.mock import MagicMock
from child_pickup.sheets import SheetsClient


def _make_client_with_values(values):
    svc = MagicMock()
    svc.spreadsheets().values().get().execute.return_value = {"values": values}
    client = SheetsClient.__new__(SheetsClient)
    client.service = svc
    client.spreadsheet_id = "sid-123"
    return client, svc


def test_read_range_returns_values():
    client, _ = _make_client_with_values([["a", "b"], ["c", "d"]])
    rows = client.read_range("Sheet1!A1:B2")
    assert rows == [["a", "b"], ["c", "d"]]


def test_read_range_defaults_to_empty():
    svc = MagicMock()
    svc.spreadsheets().values().get().execute.return_value = {}
    client = SheetsClient.__new__(SheetsClient)
    client.service = svc
    client.spreadsheet_id = "sid-123"
    assert client.read_range("Sheet1!A1:B2") == []


def test_update_range_passes_params():
    svc = MagicMock()
    client = SheetsClient.__new__(SheetsClient)
    client.service = svc
    client.spreadsheet_id = "sid-123"
    client.update_range("Sheet1!D5", [["NEW"]])
    svc.spreadsheets().values().update.assert_called_with(
        spreadsheetId="sid-123",
        range="Sheet1!D5",
        valueInputOption="RAW",
        body={"values": [["NEW"]]},
    )


def test_append_row_passes_params():
    svc = MagicMock()
    client = SheetsClient.__new__(SheetsClient)
    client.service = svc
    client.spreadsheet_id = "sid-123"
    client.append_row("Sheet1", ["a", "b", "c"])
    svc.spreadsheets().values().append.assert_called_with(
        spreadsheetId="sid-123",
        range="Sheet1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [["a", "b", "c"]]},
    )
```

- [ ] **Step 2: Run test, verify failure**

```bash
pytest tests/test_sheets.py -v
```

- [ ] **Step 3: Implement `sheets.py`**

```python
# src/child_pickup/sheets.py
from __future__ import annotations
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, service_account_info: dict, spreadsheet_id: str):
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        self.service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self.spreadsheet_id = spreadsheet_id

    def read_range(self, range_a1: str) -> list[list[str]]:
        resp = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_a1)
            .execute()
        )
        return resp.get("values", [])

    def update_range(self, range_a1: str, values: list[list]) -> None:
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_a1,
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

    def append_row(self, range_a1: str, row: list) -> None:
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=range_a1,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/sheets.py tests/test_sheets.py
git commit -m "feat(sheets): SheetsClient wrapper"
```

---

## Task 6: KidsInfo tab parser

**Files:**
- Create: `src/child_pickup/kids_info.py`
- Create: `tests/test_kids_info.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_kids_info.py
from unittest.mock import MagicMock
from child_pickup.kids_info import load_kids_info, normalize_phone


def test_normalize_phone_adds_plus_and_country():
    assert normalize_phone("(555) 123-4567") == "+15551234567"
    assert normalize_phone("555-123-4567") == "+15551234567"
    assert normalize_phone("+15551234567") == "+15551234567"
    assert normalize_phone("15551234567") == "+15551234567"
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_load_kids_info_builds_lookup():
    headers = [
        "City", "Ministry Group", "Domain",
        "Name (First & Last)", "Gender", "Child's Bday",
        "Age (yrs)", "Mother", "Mother's phone #", "Father", "Father's phone #",
        "Allergy", "If allergy, describe", "Allergic Symptoms",
        "Preferred Course of Treatment", "Insurance",
    ]
    rows = [
        headers,
        ["DC", "MG1", "D1", "Estelle Chow", "F", "01/01/2018", "6",
         "Jenny Chow", "(555) 111-1111", "Alan Chow", "555-222-2222",
         "", "", "", "", ""],
        ["DC", "MG1", "D1", "Caden Shim", "M", "01/01/2018", "6",
         "Deandra Shim", "555-333-3333", "Hanseul Shim", "555-444-4444",
         "", "", "", "", ""],
    ]
    sheets = MagicMock()
    sheets.read_range.return_value = rows

    lookup = load_kids_info(sheets, tab_name="All DMV KidsInfo")
    assert lookup["Estelle Chow"].mother_name == "Jenny Chow"
    assert lookup["Estelle Chow"].mother_phone == "+15551111111"
    assert lookup["Estelle Chow"].father_phone == "+15552222222"
    assert lookup["Caden Shim"].father_name == "Hanseul Shim"
    assert lookup["Caden Shim"].mother_phone == "+15553333333"
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `kids_info.py`**

```python
# src/child_pickup/kids_info.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class KidInfo:
    full_name: str
    mother_name: str
    mother_phone: Optional[str]
    father_name: str
    father_phone: Optional[str]


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    # Fallback: return whatever we got, prefixed with +
    return "+" + digits


REQUIRED_HEADERS = {
    "Name (First & Last)": "full_name",
    "Mother": "mother_name",
    "Mother's phone #": "mother_phone",
    "Father": "father_name",
    "Father's phone #": "father_phone",
}


def load_kids_info(sheets_client, tab_name: str) -> dict[str, KidInfo]:
    rows = sheets_client.read_range(f"'{tab_name}'!A1:Z1000")
    if not rows:
        return {}
    headers = rows[0]
    try:
        idx = {label: headers.index(label) for label in REQUIRED_HEADERS}
    except ValueError as e:
        raise ValueError(f"KidsInfo tab missing required header: {e}")

    out: dict[str, KidInfo] = {}
    for row in rows[1:]:
        if len(row) <= idx["Name (First & Last)"]:
            continue
        full_name = row[idx["Name (First & Last)"]].strip()
        if not full_name:
            continue
        out[full_name] = KidInfo(
            full_name=full_name,
            mother_name=_get(row, idx["Mother"]),
            mother_phone=normalize_phone(_get(row, idx["Mother's phone #"])),
            father_name=_get(row, idx["Father"]),
            father_phone=normalize_phone(_get(row, idx["Father's phone #"])),
        )
    return out


def _get(row: list, idx: int) -> str:
    return row[idx].strip() if idx < len(row) and row[idx] else ""
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/kids_info.py tests/test_kids_info.py
git commit -m "feat(kids_info): parse KidsInfo tab into name→parents lookup"
```

---

## Task 7: Pickup Schedule reader and grouping

**Files:**
- Create: `src/child_pickup/pickup_schedule.py`
- Create: `tests/test_pickup_schedule.py`

The pickup schedule reader does three jobs: (1) find the column index for a target date like `"4/12"`, (2) collect blank rows in that column, (3) group them by `ON-GOING` value joined with KidsInfo for phones.

- [ ] **Step 1: Write failing test**

```python
# tests/test_pickup_schedule.py
from datetime import date
from unittest.mock import MagicMock
from child_pickup.pickup_schedule import (
    find_date_column_index,
    read_blank_rows,
    group_blank_rows,
)
from child_pickup.kids_info import KidInfo


HEADERS = ["Last Name", "Full Name", "ON-GOING", "4/12", "4/19", "4/26"]


def test_find_date_column_index():
    assert find_date_column_index(HEADERS, date(2026, 4, 12)) == 3
    assert find_date_column_index(HEADERS, date(2026, 4, 19)) == 4


def test_find_date_column_index_missing():
    assert find_date_column_index(HEADERS, date(2026, 5, 3)) is None


def test_read_blank_rows_returns_only_blank_cells():
    rows = [
        HEADERS,
        ["Chow", "Estelle Chow", "Jenny or Alan", "Jenny/Alan", "", ""],
        ["Shim", "Caden Shim", "Hanseul or Deandra", "", "", ""],
        ["Shim", "Easton Shim", "Hanseul or Deandra", "", "", ""],
        ["Lee", "Alden Lee", "Bliss or Liny", "", "", ""],
    ]
    children = read_blank_rows(rows, col_index=3)
    names = [c.full_name for c in children]
    assert "Estelle Chow" not in names  # filled, skip
    assert names == ["Caden Shim", "Easton Shim", "Alden Lee"]
    assert children[0].row_number == 3  # 1-indexed; header row=1, Chow row=2
    assert children[0].ongoing_person == "Hanseul or Deandra"


def test_group_blank_rows_groups_by_ongoing_and_dedupes_phones():
    children = [
        _child("Caden Shim", 3, "Hanseul or Deandra"),
        _child("Easton Shim", 4, "Hanseul or Deandra"),
        _child("Alden Lee", 5, "Bliss or Liny"),
    ]
    kids_info = {
        "Caden Shim": KidInfo("Caden Shim", "Deandra Shim", "+15551110000",
                              "Hanseul Shim", "+15552220000"),
        "Easton Shim": KidInfo("Easton Shim", "Deandra Shim", "+15551110000",
                               "Hanseul Shim", "+15552220000"),
        "Alden Lee": KidInfo("Alden Lee", "Liny Lee", "+15553330000",
                             "Bliss Lee", "+15554440000"),
    }
    groups = group_blank_rows(children, kids_info)
    assert len(groups) == 2
    shim = next(g for g in groups if g.ongoing_person == "Hanseul or Deandra")
    assert shim.unique_phones() == ["+15551110000", "+15552220000"]
    assert sorted(shim.child_names()) == ["Caden Shim", "Easton Shim"]
    assert set(shim.parent_names) == {"Deandra Shim", "Hanseul Shim"}


def test_group_skips_children_with_no_phones():
    children = [_child("Ghost Kid", 10, "Nobody")]
    kids_info = {"Ghost Kid": KidInfo("Ghost Kid", "", None, "", None)}
    groups = group_blank_rows(children, kids_info)
    assert groups == []


def _child(name, row, ongoing):
    from child_pickup.models import Child
    last = name.split()[-1]
    return Child(full_name=name, last_name=last, row_number=row, ongoing_person=ongoing)
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `pickup_schedule.py`**

```python
# src/child_pickup/pickup_schedule.py
from __future__ import annotations
from datetime import date
from typing import Optional

from .models import Child, Group
from .kids_info import KidInfo


def find_date_column_index(headers: list[str], target: date) -> Optional[int]:
    """Return 0-indexed column for the target date, or None if not found.

    Sheet headers use M/D format without zero padding (e.g. '4/12').
    """
    target_str = f"{target.month}/{target.day}"
    for i, h in enumerate(headers):
        if str(h).strip() == target_str:
            return i
    return None


def read_blank_rows(rows: list[list[str]], col_index: int) -> list[Child]:
    """Given raw sheet rows (first row is headers), return Child records
    for rows where the target column is blank.

    Assumes columns: Last Name=0, Full Name=1, ON-GOING=2, then date columns.
    Header row is row 1 (1-indexed); data starts at row 2.
    """
    out: list[Child] = []
    for sheet_row_idx, row in enumerate(rows[1:], start=2):
        if len(row) < 3:
            continue
        last_name = row[0].strip() if row[0] else ""
        full_name = row[1].strip() if row[1] else ""
        ongoing = row[2].strip() if row[2] else ""
        if not full_name:
            continue
        cell = row[col_index].strip() if col_index < len(row) and row[col_index] else ""
        if cell:
            continue  # already filled; skip
        out.append(
            Child(
                full_name=full_name,
                last_name=last_name,
                row_number=sheet_row_idx,
                ongoing_person=ongoing,
            )
        )
    return out


def group_blank_rows(
    children: list[Child], kids_info: dict[str, KidInfo]
) -> list[Group]:
    """Group children by ongoing_person, then collect parent phones from kids_info.

    Drops groups where no parent phones could be resolved.
    """
    by_ongoing: dict[str, list[Child]] = {}
    for c in children:
        by_ongoing.setdefault(c.ongoing_person, []).append(c)

    groups: list[Group] = []
    for ongoing, kids in by_ongoing.items():
        phones: list[str] = []
        names: list[str] = []
        for c in kids:
            info = kids_info.get(c.full_name)
            if not info:
                continue
            for phone, pname in (
                (info.mother_phone, info.mother_name),
                (info.father_phone, info.father_name),
            ):
                if phone:
                    phones.append(phone)
                    names.append(pname or "")
        if not phones:
            continue
        groups.append(
            Group(
                ongoing_person=ongoing,
                children=kids,
                parent_phones=phones,
                parent_names=names,
            )
        )
    return groups
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/pickup_schedule.py tests/test_pickup_schedule.py
git commit -m "feat(pickup_schedule): column lookup, blank detection, grouping"
```

---

## Task 8: Pending Confirmations tab

**Files:**
- Create: `src/child_pickup/pending.py`
- Create: `tests/test_pending.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_pending.py
from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.pending import PendingStore
from child_pickup.models import PendingConfirmation


def test_list_pending_for_date_filters_by_date_and_status():
    sheets = MagicMock()
    sheets.read_range.return_value = [
        PendingConfirmation.SHEET_HEADERS,
        [
            "id-1", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "3,4", "Caden Shim,Easton Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
        [
            "id-2", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "5", "Alden Lee", "Bliss or Liny",
            "+15552220000", "Bliss Lee", "confirmed",
            "2026-04-11T22:00:00+00:00", "yes", "",
        ],
        [
            "id-3", "2026-04-04T21:00:00+00:00", "2026-04-05",
            "3", "Caden Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
    ]
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    pending = store.list_pending(date(2026, 4, 12))
    assert len(pending) == 1
    assert pending[0].id == "id-1"


def test_append_confirmation():
    sheets = MagicMock()
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    pc = PendingConfirmation(
        id="new-1",
        sent_at=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
        pickup_date=date(2026, 4, 12),
        sheet_row_numbers=[3, 4],
        children_names=["Caden Shim", "Easton Shim"],
        ongoing_person="Hanseul or Deandra",
        parent_phones=["+15551110000"],
        parent_names=["Hanseul Shim"],
        status="pending",
    )
    store.append(pc)
    sheets.append_row.assert_called_once()
    _, called_args = sheets.append_row.call_args
    # called positionally in impl; accept either form
    args = sheets.append_row.call_args.args
    assert args[0] == "'Pending Confirmations'!A:L"
    assert args[1][0] == "new-1"


def test_find_pending_for_phone_returns_most_recent():
    sheets = MagicMock()
    sheets.read_range.return_value = [
        PendingConfirmation.SHEET_HEADERS,
        [
            "id-old", "2026-04-11T20:00:00+00:00", "2026-04-12",
            "3", "Caden Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
        [
            "id-new", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "4", "Easton Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
    ]
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    found = store.find_pending_for_phone("+15551110000", date(2026, 4, 12))
    assert found.id == "id-new"


def test_update_status_rewrites_row():
    sheets = MagicMock()
    sheets.read_range.return_value = [
        PendingConfirmation.SHEET_HEADERS,
        [
            "id-1", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "3", "Caden Shim", "Hanseul or Deandra",
            "+15551110000", "Hanseul Shim", "pending", "", "", "",
        ],
    ]
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    store.mark_resolved(
        "id-1",
        status="confirmed",
        resolved_at=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
        reply_text="yes",
        resolved_value="",
    )
    sheets.update_range.assert_called_once()
    rng = sheets.update_range.call_args.args[0]
    assert "'Pending Confirmations'" in rng
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `pending.py`**

```python
# src/child_pickup/pending.py
from __future__ import annotations
from datetime import date, datetime
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
            sent_at=datetime.now(tz=__import__("datetime").timezone.utc),
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
```

Add to the Task 8 test file:

```python
def test_append_send_errors_writes_sentinel_row():
    sheets = MagicMock()
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    store.append_send_errors(date(2026, 4, 12), ["no phones for Ghost Kid", "twilio 500"])
    assert sheets.append_row.call_count == 1
    row = sheets.append_row.call_args.args[1]
    assert row[0] == "send-errors:2026-04-12"
    assert row[8] == "send_errors"
    assert "Ghost Kid" in row[10]


def test_get_send_errors_returns_lines():
    sheets = MagicMock()
    sheets.read_range.return_value = [
        PendingConfirmation.SHEET_HEADERS,
        [
            "send-errors:2026-04-12", "2026-04-11T21:00:00+00:00", "2026-04-12",
            "", "", "", "", "", "send_errors", "",
            "no phones for Ghost Kid\ntwilio 500", "",
        ],
    ]
    store = PendingStore(sheets, tab_name="Pending Confirmations")
    assert store.get_send_errors(date(2026, 4, 12)) == [
        "no phones for Ghost Kid",
        "twilio 500",
    ]
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/pending.py tests/test_pending.py
git commit -m "feat(pending): PendingStore for Pending Confirmations tab"
```

---

## Task 9: TwilioClient (send + verify + compose)

**Files:**
- Create: `src/child_pickup/twilio_client.py`
- Create: `tests/test_twilio_client.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_twilio_client.py
from unittest.mock import MagicMock, patch
from child_pickup.twilio_client import TwilioClient, compose_sms_body
from child_pickup.models import Group, Child


def _group(ongoing, kids, phones, names):
    children = [Child(full_name=n, last_name=n.split()[-1], row_number=i+2,
                      ongoing_person=ongoing) for i, n in enumerate(kids)]
    return Group(ongoing_person=ongoing, children=children,
                 parent_phones=phones, parent_names=names)


def test_compose_single_child_single_parent():
    g = _group("Shara", ["Estelle Chow"], ["+15551110000"], ["Shara Smith"])
    body = compose_sms_body(g, pickup_md="4/12", coordinator="DMV pickup coordinator")
    assert "Confirming Shara is picking up Estelle Chow tomorrow (4/12)" in body
    assert "Reply YES" in body
    assert "One of you" not in body


def test_compose_multiple_children_same_person():
    g = _group(
        "Hanseul or Deandra",
        ["Caden Shim", "Easton Shim", "Mason Shim"],
        ["+15551110000"],
        ["Hanseul Shim"],
    )
    body = compose_sms_body(g, pickup_md="4/12", coordinator="DMV pickup coordinator")
    assert "Caden Shim, Easton Shim, and Mason Shim" in body
    assert "pick them up instead" in body


def test_compose_two_parent_message_adds_prefix():
    g = _group("Jenny or Alan", ["Estelle Chow"], ["+15551110000", "+15552220000"],
               ["Jenny Chow", "Alan Chow"])
    body = compose_sms_body(g, pickup_md="4/12", coordinator="DMV pickup coordinator")
    assert "One of you" in body


def test_client_sends_via_twilio_sdk():
    with patch("child_pickup.twilio_client.Client") as MockClient:
        inst = MockClient.return_value
        client = TwilioClient(
            account_sid="AC1", auth_token="TOK", from_number="+15550000000",
            dry_run=False,
        )
        client.send("+15551110000", "hello")
        inst.messages.create.assert_called_with(
            body="hello", from_="+15550000000", to="+15551110000"
        )


def test_client_dry_run_skips_send(caplog):
    with patch("child_pickup.twilio_client.Client") as MockClient:
        client = TwilioClient(
            account_sid="AC1", auth_token="TOK", from_number="+15550000000",
            dry_run=True,
        )
        client.send("+15551110000", "hello")
        MockClient.return_value.messages.create.assert_not_called()


def test_signature_validation_delegates_to_twilio_validator():
    with patch("child_pickup.twilio_client.RequestValidator") as MockValidator:
        MockValidator.return_value.validate.return_value = True
        client = TwilioClient(
            account_sid="AC1", auth_token="TOK", from_number="+15550000000",
            dry_run=False,
        )
        ok = client.validate_signature(
            url="https://example.com/sms",
            params={"From": "+15551110000", "Body": "yes"},
            signature="sig123",
        )
        assert ok is True
        MockValidator.return_value.validate.assert_called_with(
            "https://example.com/sms", {"From": "+15551110000", "Body": "yes"}, "sig123"
        )
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `twilio_client.py`**

```python
# src/child_pickup/twilio_client.py
from __future__ import annotations
from twilio.rest import Client
from twilio.request_validator import RequestValidator

from .logging_setup import get_logger
from .models import Group

log = get_logger(__name__)


def compose_sms_body(group: Group, pickup_md: str, coordinator: str) -> str:
    children = group.children
    unique_phones = group.unique_phones()
    two_parents = len(unique_phones) >= 2
    prefix = f"Hi, this is the {coordinator}."
    confirming = (
        f"One of you — confirming {group.ongoing_person}"
        if two_parents
        else f"Confirming {group.ongoing_person}"
    )

    if len(children) == 1:
        kids_phrase = children[0].full_name
        them = "them"
    elif len(children) == 2:
        kids_phrase = f"{children[0].full_name} and {children[1].full_name}"
        them = "them"
    else:
        kids_phrase = (
            ", ".join(c.full_name for c in children[:-1])
            + f", and {children[-1].full_name}"
        )
        them = "them"

    return (
        f"{prefix} {confirming} is picking up {kids_phrase} tomorrow ({pickup_md}). "
        f"Reply YES to confirm, or reply with who will pick {them} up instead."
    )


class TwilioClient:
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        dry_run: bool = False,
    ):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.dry_run = dry_run
        self._client = Client(account_sid, auth_token) if not dry_run else None
        self._validator = RequestValidator(auth_token)

    def send(self, to: str, body: str) -> None:
        if self.dry_run:
            log.info("dry_run_sms", to=to, body=body)
            return
        self._client.messages.create(body=body, from_=self.from_number, to=to)

    def validate_signature(self, url: str, params: dict, signature: str) -> bool:
        return self._validator.validate(url, params, signature)
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/twilio_client.py tests/test_twilio_client.py
git commit -m "feat(twilio): client wrapper + SMS body composer"
```

---

## Task 10: Reply parser (regex + Claude Haiku fallback)

**Files:**
- Create: `src/child_pickup/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_parser.py
import json
from unittest.mock import MagicMock, patch
from child_pickup.parser import ReplyParser, ParseResult


def test_regex_yes_variants_return_confirm():
    parser = ReplyParser(anthropic_api_key="sk-ant-test")
    for body in ["YES", "yes", "Y", "Yep", "yeah", " YUP ", "OK", "okay.", "Sure!"]:
        r = parser.parse(body, ongoing_person="Hanseul or Deandra",
                         children_names=["Caden Shim"])
        assert r.action == "confirm", f"{body} should confirm"
        assert r.new_pickup_person is None


@patch("child_pickup.parser.anthropic.Anthropic")
def test_llm_fallback_on_non_matching_reply(mock_anth):
    mock_client = mock_anth.return_value
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(
            {"action": "change", "new_pickup_person": "Grandma Linda"}
        ))]
    )
    parser = ReplyParser(anthropic_api_key="sk-ant-test")
    r = parser.parse(
        "actually my mom Linda is grabbing him",
        ongoing_person="Hanseul or Deandra",
        children_names=["Caden Shim"],
    )
    assert r.action == "change"
    assert r.new_pickup_person == "Grandma Linda"


@patch("child_pickup.parser.anthropic.Anthropic")
def test_llm_ambiguous_response(mock_anth):
    mock_client = mock_anth.return_value
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(
            {"action": "ambiguous", "new_pickup_person": None}
        ))]
    )
    parser = ReplyParser(anthropic_api_key="sk-ant-test")
    r = parser.parse("hmm", ongoing_person="Shara", children_names=["Estelle Chow"])
    assert r.action == "ambiguous"


@patch("child_pickup.parser.anthropic.Anthropic")
def test_llm_malformed_json_becomes_ambiguous(mock_anth):
    mock_client = mock_anth.return_value
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="not json at all")]
    )
    parser = ReplyParser(anthropic_api_key="sk-ant-test")
    r = parser.parse("?", ongoing_person="Shara", children_names=["Estelle Chow"])
    assert r.action == "ambiguous"
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `parser.py`**

```python
# src/child_pickup/parser.py
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Optional

import anthropic

from .logging_setup import get_logger

log = get_logger(__name__)

YES_REGEX = re.compile(r"^(YES|Y|YEP|YEAH|YUP|CONFIRM|CONFIRMED|OK|OKAY|SURE)$")


@dataclass
class ParseResult:
    action: str  # confirm | change | ambiguous
    new_pickup_person: Optional[str] = None


LLM_SYSTEM_PROMPT = """You parse SMS replies from parents about who is picking up their child from an afterschool program.

You will receive:
- The default pickup person ("ongoing_person")
- The children's names
- The parent's reply text

Classify the reply into one of three actions:
- "confirm": the parent is confirming that the ongoing person is picking up (e.g. "yes", "sounds good", "that's correct")
- "change": the parent is saying someone else is picking up instead. Extract the name.
- "ambiguous": the reply is unclear, asks a question, or doesn't answer.

Respond with ONLY a JSON object of the form:
{"action": "confirm" | "change" | "ambiguous", "new_pickup_person": string | null}

If action is "change", new_pickup_person must be a non-empty name.
Otherwise new_pickup_person must be null.
"""


class ReplyParser:
    def __init__(self, anthropic_api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self._client = anthropic.Anthropic(api_key=anthropic_api_key)
        self._model = model

    def parse(
        self,
        body: str,
        *,
        ongoing_person: str,
        children_names: list[str],
    ) -> ParseResult:
        cleaned = _clean_for_regex(body)
        if YES_REGEX.match(cleaned):
            return ParseResult(action="confirm")
        return self._llm_parse(body, ongoing_person, children_names)

    def _llm_parse(
        self, body: str, ongoing_person: str, children_names: list[str]
    ) -> ParseResult:
        user_msg = (
            f"ongoing_person: {ongoing_person}\n"
            f"children: {', '.join(children_names)}\n"
            f"reply: {body}"
        )
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=128,
                system=LLM_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text.strip()
            data = json.loads(text)
            action = data.get("action")
            if action not in {"confirm", "change", "ambiguous"}:
                log.warning("parser_bad_action", action=action)
                return ParseResult(action="ambiguous")
            if action == "change":
                name = (data.get("new_pickup_person") or "").strip()
                if not name:
                    return ParseResult(action="ambiguous")
                return ParseResult(action="change", new_pickup_person=name)
            return ParseResult(action=action)
        except Exception as e:
            log.warning("parser_llm_error", error=str(e))
            return ParseResult(action="ambiguous")


def _clean_for_regex(body: str) -> str:
    # Strip whitespace and trailing/leading punctuation; uppercase
    return re.sub(r"[^\w]", "", body).upper()
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/parser.py tests/test_parser.py
git commit -m "feat(parser): regex fast path + Claude Haiku fallback"
```

---

## Task 11: EmailClient (SES summary)

**Files:**
- Create: `src/child_pickup/email_client.py`
- Create: `tests/test_email_client.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_email_client.py
from datetime import date
from unittest.mock import MagicMock, patch
from child_pickup.email_client import EmailClient, SummaryData, GroupOutcome


@patch("child_pickup.email_client.boto3")
def test_send_summary_calls_ses(mock_boto3):
    mock_ses = MagicMock()
    mock_boto3.client.return_value = mock_ses
    client = EmailClient(
        sender="pickup@dmv.org",
        recipients=["a@b.com", "c@d.com"],
        region="us-east-1",
        dry_run=False,
    )
    data = SummaryData(
        pickup_date=date(2026, 4, 12),
        confirmed=[GroupOutcome("Hanseul or Deandra", ["Caden Shim"], None)],
        changed=[GroupOutcome("Grandma Linda", ["Estelle Chow"], "Jenny or Alan")],
        no_response=[GroupOutcome("Shara", ["Alice"], None, parent_contacts=[("Jen", "+15551110000")])],
        send_errors=["no phones for Ghost Kid"],
    )
    client.send_summary(data)
    mock_ses.send_email.assert_called_once()
    kwargs = mock_ses.send_email.call_args.kwargs
    assert kwargs["Source"] == "pickup@dmv.org"
    assert set(kwargs["Destination"]["ToAddresses"]) == {"a@b.com", "c@d.com"}
    body = kwargs["Message"]["Body"]["Text"]["Data"]
    assert "2026-04-12" in body
    assert "Caden Shim" in body
    assert "Grandma Linda" in body
    assert "Shara" in body
    assert "+15551110000" in body
    assert "Ghost Kid" in body


@patch("child_pickup.email_client.boto3")
def test_send_summary_dry_run_skips(mock_boto3):
    client = EmailClient(
        sender="pickup@dmv.org",
        recipients=["a@b.com"],
        region="us-east-1",
        dry_run=True,
    )
    data = SummaryData(pickup_date=date(2026, 4, 12), confirmed=[], changed=[],
                       no_response=[], send_errors=[])
    client.send_summary(data)
    mock_boto3.client.assert_not_called()
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `email_client.py`**

```python
# src/child_pickup/email_client.py
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
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/email_client.py tests/test_email_client.py
git commit -m "feat(email): SES summary email client"
```

---

## Task 12: Send flow

**Files:**
- Create: `src/child_pickup/send.py`
- Create: `tests/test_send.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_send.py
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from child_pickup.send import run_send_flow, SendResult
from child_pickup.models import Child, Group
from child_pickup.kids_info import KidInfo


def _pickup_rows():
    return [
        ["Last Name", "Full Name", "ON-GOING", "4/12", "4/19"],
        ["Chow", "Estelle Chow", "Jenny or Alan", "Jenny/Alan", ""],
        ["Shim", "Caden Shim", "Hanseul or Deandra", "", ""],
        ["Shim", "Easton Shim", "Hanseul or Deandra", "", ""],
        ["Lee", "Alden Lee", "Bliss or Liny", "", ""],
    ]


def _kids_info_rows():
    headers = [
        "City", "Ministry Group", "Domain",
        "Name (First & Last)", "Gender", "Bday", "Age",
        "Mother", "Mother's phone #", "Father", "Father's phone #",
        "Allergy", "Desc", "Symp", "Treat", "Ins",
    ]
    return [
        headers,
        ["", "", "", "Caden Shim", "M", "", "",
         "Deandra Shim", "555-111-1111", "Hanseul Shim", "555-222-2222",
         "", "", "", "", ""],
        ["", "", "", "Easton Shim", "M", "", "",
         "Deandra Shim", "555-111-1111", "Hanseul Shim", "555-222-2222",
         "", "", "", "", ""],
        ["", "", "", "Alden Lee", "M", "", "",
         "Liny Lee", "555-333-3333", "Bliss Lee", "555-444-4444",
         "", "", "", "", ""],
    ]


def test_send_flow_skips_existing_pending_and_sends_new():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
        "'Pending Confirmations'!A:L": [],
    }[rng]

    twilio = MagicMock()
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pending_tab="Pending Confirmations",
        target_date=date(2026, 4, 12),
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
    )

    # Two groups: Shim (2 kids, 2 parents) and Lee (1 kid, 2 parents)
    assert result.groups_sent == 2
    assert twilio.send.call_count == 4  # 2 groups * 2 parents
    # Pending rows appended
    assert sheets.append_row.call_count == 2


def test_send_flow_skips_group_already_pending():
    pending_rows = [
        [
            "id-existing", "2026-04-11T20:00:00+00:00", "2026-04-12",
            "3,4", "Caden Shim,Easton Shim", "Hanseul or Deandra",
            "+15552221111", "Hanseul Shim", "pending", "", "", "",
        ],
    ]
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
        "'Pending Confirmations'!A:L": [
            __import__("child_pickup.models", fromlist=["PendingConfirmation"])
            .PendingConfirmation.SHEET_HEADERS
        ] + pending_rows,
    }[rng]

    twilio = MagicMock()
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pending_tab="Pending Confirmations",
        target_date=date(2026, 4, 12),
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
    )

    # Only the Lee group should have been sent
    assert result.groups_sent == 1
    assert sheets.append_row.call_count == 1


def test_send_flow_aborts_if_column_missing():
    sheets = MagicMock()
    sheets.read_range.side_effect = lambda rng: {
        "'Pickup Schedule'!A1:Z1000": _pickup_rows(),
        "'All DMV KidsInfo'!A1:Z1000": _kids_info_rows(),
        "'Pending Confirmations'!A:L": [],
    }[rng]
    twilio = MagicMock()
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab="Pickup Schedule",
        kids_info_tab="All DMV KidsInfo",
        pending_tab="Pending Confirmations",
        target_date=date(2026, 5, 3),  # not in headers
        coordinator_name="DMV pickup coordinator",
        now=datetime(2026, 5, 2, 21, 0, tzinfo=timezone.utc),
    )
    assert result.aborted is True
    twilio.send.assert_not_called()
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `send.py`**

```python
# src/child_pickup/send.py
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from .kids_info import load_kids_info
from .logging_setup import get_logger
from .models import Group, PendingConfirmation
from .pending import PendingStore
from .pickup_schedule import (
    find_date_column_index,
    group_blank_rows,
    read_blank_rows,
)
from .twilio_client import TwilioClient, compose_sms_body

log = get_logger(__name__)


@dataclass
class SendResult:
    groups_sent: int = 0
    groups_skipped: int = 0
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
    pending_tab: str,
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

    kids_info = load_kids_info(sheets, kids_info_tab)
    blank_children = read_blank_rows(pickup_rows, col_index)

    # Track names missing from KidsInfo for the summary
    for c in blank_children:
        if c.full_name not in kids_info:
            result.send_errors.append(f"no KidsInfo entry for {c.full_name}")

    groups = group_blank_rows(blank_children, kids_info)

    # Identify children we had blanks for but couldn't put in any group (no phones)
    in_groups = {c.full_name for g in groups for c in g.children}
    for c in blank_children:
        if c.full_name not in in_groups and c.full_name in kids_info:
            result.send_errors.append(f"no parent phones for {c.full_name}")

    store = PendingStore(sheets, pending_tab)
    pickup_md = f"{target_date.month}/{target_date.day}"

    for group in groups:
        if store.group_already_sent(target_date, group.row_numbers()):
            result.groups_skipped += 1
            continue

        pc = PendingConfirmation(
            id=str(uuid.uuid4()),
            sent_at=now,
            pickup_date=target_date,
            sheet_row_numbers=group.row_numbers(),
            children_names=group.child_names(),
            ongoing_person=group.ongoing_person,
            parent_phones=group.unique_phones(),
            parent_names=list(dict.fromkeys(group.parent_names)),
            status="pending",
        )
        store.append(pc)

        body = compose_sms_body(group, pickup_md=pickup_md, coordinator=coordinator_name)
        for phone in pc.parent_phones:
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
            pending_id=pc.id,
            ongoing=group.ongoing_person,
            children=group.child_names(),
            phones=pc.parent_phones,
        )

    # Persist send errors so cutoff can include them in the summary email.
    if result.send_errors:
        store.append_send_errors(target_date, result.send_errors)

    return result
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/send.py tests/test_send.py
git commit -m "feat(send): send flow orchestration"
```

---

## Task 13: Reply flow

**Files:**
- Create: `src/child_pickup/reply.py`
- Create: `tests/test_reply.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_reply.py
from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.reply import handle_reply, ReplyOutcome
from child_pickup.models import PendingConfirmation
from child_pickup.parser import ParseResult


def _make_pending():
    return PendingConfirmation(
        id="id-1",
        sent_at=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
        pickup_date=date(2026, 4, 12),
        sheet_row_numbers=[3, 4],
        children_names=["Caden Shim", "Easton Shim"],
        ongoing_person="Hanseul or Deandra",
        parent_phones=["+15551110000", "+15552220000"],
        parent_names=["Hanseul Shim", "Deandra Shim"],
        status="pending",
    )


def _find_pending_value_for_column(col_index):
    # Column 3 = D, column 4 = E, etc (0-indexed from col 0 = A)
    return chr(ord("A") + col_index)


def test_confirm_writes_blank_and_marks_confirmed():
    store = MagicMock()
    store.find_pending_for_phone.return_value = _make_pending()
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="confirm")
    sheets = MagicMock()

    outcome = handle_reply(
        sheets=sheets,
        store=store,
        parser=parser,
        from_phone="+15551110000",
        body="yes",
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,  # '4/12' column (0-indexed: D)
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "confirm"
    # Blank written to D3 and D4
    calls = sheets.update_range.call_args_list
    ranges = [c.args[0] for c in calls]
    assert "'Pickup Schedule'!D3" in ranges
    assert "'Pickup Schedule'!D4" in ranges
    for c in calls:
        assert c.args[1] == [[""]]
    store.mark_resolved.assert_called_once()
    assert store.mark_resolved.call_args.kwargs["status"] == "confirmed"


def test_change_writes_new_name_to_cells():
    store = MagicMock()
    store.find_pending_for_phone.return_value = _make_pending()
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="change", new_pickup_person="Grandma Linda")
    sheets = MagicMock()

    outcome = handle_reply(
        sheets=sheets,
        store=store,
        parser=parser,
        from_phone="+15551110000",
        body="my mom Linda",
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "change"
    for c in sheets.update_range.call_args_list:
        assert c.args[1] == [["Grandma Linda"]]
    assert store.mark_resolved.call_args.kwargs["status"] == "changed"
    assert store.mark_resolved.call_args.kwargs["resolved_value"] == "Grandma Linda"


def test_ambiguous_leaves_row_pending_and_returns_reply_text():
    store = MagicMock()
    store.find_pending_for_phone.return_value = _make_pending()
    parser = MagicMock()
    parser.parse.return_value = ParseResult(action="ambiguous")
    sheets = MagicMock()

    outcome = handle_reply(
        sheets=sheets,
        store=store,
        parser=parser,
        from_phone="+15551110000",
        body="huh?",
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )

    assert outcome.action == "ambiguous"
    sheets.update_range.assert_not_called()
    store.mark_resolved.assert_not_called()
    assert "Hanseul or Deandra" in outcome.reply_text


def test_no_matching_pending_returns_unmatched():
    store = MagicMock()
    store.find_pending_for_phone.return_value = None
    parser = MagicMock()
    outcome = handle_reply(
        sheets=MagicMock(),
        store=store,
        parser=parser,
        from_phone="+15559999999",
        body="yes",
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        pickup_date=date(2026, 4, 12),
        now=datetime(2026, 4, 11, 22, 0, tzinfo=timezone.utc),
    )
    assert outcome.action == "unmatched"
    assert "don't have a pending" in outcome.reply_text.lower()
    parser.parse.assert_not_called()
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `reply.py`**

```python
# src/child_pickup/reply.py
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
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/reply.py tests/test_reply.py
git commit -m "feat(reply): reply flow orchestration"
```

---

## Task 14: Cutoff flow

**Files:**
- Create: `src/child_pickup/cutoff.py`
- Create: `tests/test_cutoff.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cutoff.py
from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from child_pickup.cutoff import run_cutoff_flow
from child_pickup.models import PendingConfirmation
from child_pickup.email_client import SummaryData


def _pending(id, status):
    return PendingConfirmation(
        id=id,
        sent_at=datetime(2026, 4, 11, 21, 0, tzinfo=timezone.utc),
        pickup_date=date(2026, 4, 12),
        sheet_row_numbers=[3, 4],
        children_names=["Caden Shim", "Easton Shim"],
        ongoing_person="Hanseul or Deandra",
        parent_phones=["+15551110000"],
        parent_names=["Hanseul Shim"],
        status=status,
    )


def test_cutoff_writes_no_response_and_marks_rows():
    sheets = MagicMock()
    store = MagicMock()
    store.list_pending.return_value = [_pending("id-1", "pending")]
    # Also provide full history for the summary
    store._read_all.return_value = [
        (2, _pending("id-confirmed", "confirmed")),
        (3, _pending("id-1", "no_response")),  # after update
    ]
    store.get_send_errors.return_value = ["no phones for Ghost Kid"]
    email = MagicMock()

    result = run_cutoff_flow(
        sheets=sheets,
        store=store,
        email=email,
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        target_date=date(2026, 4, 12),
        now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
    )

    # Wrote NO RESPONSE to D3 and D4
    ranges = [c.args[0] for c in sheets.update_range.call_args_list]
    assert "'Pickup Schedule'!D3" in ranges
    assert "'Pickup Schedule'!D4" in ranges
    for c in sheets.update_range.call_args_list:
        assert c.args[1] == [["NO RESPONSE"]]

    store.mark_resolved.assert_called_once()
    assert store.mark_resolved.call_args.kwargs["status"] == "no_response"
    assert store.mark_resolved.call_args.kwargs["resolved_value"] == "NO RESPONSE"

    email.send_summary.assert_called_once()
    data: SummaryData = email.send_summary.call_args.args[0]
    assert data.pickup_date == date(2026, 4, 12)
    assert "no phones for Ghost Kid" in data.send_errors


def test_cutoff_still_emails_when_no_pending():
    sheets = MagicMock()
    store = MagicMock()
    store.list_pending.return_value = []
    store._read_all.return_value = []
    store.get_send_errors.return_value = []
    email = MagicMock()

    run_cutoff_flow(
        sheets=sheets,
        store=store,
        email=email,
        pickup_tab="Pickup Schedule",
        pickup_col_index=3,
        target_date=date(2026, 4, 12),
        now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
    )
    email.send_summary.assert_called_once()
    sheets.update_range.assert_not_called()
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `cutoff.py`**

```python
# src/child_pickup/cutoff.py
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
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/cutoff.py tests/test_cutoff.py
git commit -m "feat(cutoff): cutoff flow + summary build"
```

---

## Task 15: Handler dispatch

**Files:**
- Create: `src/child_pickup/handler.py`
- Create: `tests/test_handler.py`

The Lambda entry point inspects the event and dispatches. Three event shapes:
1. EventBridge schedule with `detail-type: "Scheduled Event"` and a custom `detail.flow` field (`send` or `cutoff`).
2. API Gateway HTTP API event (`requestContext.http.method == "POST"`).

- [ ] **Step 1: Write failing test**

```python
# tests/test_handler.py
from unittest.mock import MagicMock, patch
import base64
import json


def _scheduled_event(flow):
    return {"source": "aws.events", "detail-type": "Scheduled Event", "detail": {"flow": flow}}


def _api_gateway_event(body_dict, signature="sig"):
    body = "&".join(f"{k}={v}" for k, v in body_dict.items())
    return {
        "requestContext": {"http": {"method": "POST", "path": "/sms"}},
        "headers": {"x-twilio-signature": signature},
        "rawPath": "/sms",
        "body": body,
        "isBase64Encoded": False,
    }


@patch("child_pickup.handler._run_send")
@patch("child_pickup.handler._run_cutoff")
@patch("child_pickup.handler._handle_webhook")
def test_dispatches_send(mock_webhook, mock_cutoff, mock_send):
    from child_pickup.handler import lambda_handler
    lambda_handler(_scheduled_event("send"), None)
    mock_send.assert_called_once()
    mock_cutoff.assert_not_called()
    mock_webhook.assert_not_called()


@patch("child_pickup.handler._run_send")
@patch("child_pickup.handler._run_cutoff")
@patch("child_pickup.handler._handle_webhook")
def test_dispatches_cutoff(mock_webhook, mock_cutoff, mock_send):
    from child_pickup.handler import lambda_handler
    lambda_handler(_scheduled_event("cutoff"), None)
    mock_cutoff.assert_called_once()


@patch("child_pickup.handler._run_send")
@patch("child_pickup.handler._run_cutoff")
@patch("child_pickup.handler._handle_webhook")
def test_dispatches_webhook(mock_webhook, mock_cutoff, mock_send):
    from child_pickup.handler import lambda_handler
    mock_webhook.return_value = {"statusCode": 200, "body": "<Response/>"}
    resp = lambda_handler(_api_gateway_event({"From": "+15551110000", "Body": "yes"}), None)
    mock_webhook.assert_called_once()
    assert resp["statusCode"] == 200
```

- [ ] **Step 2: Run test, verify failure**

- [ ] **Step 3: Implement `handler.py`**

```python
# src/child_pickup/handler.py
from __future__ import annotations
import base64
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

from .config import get_config
from .email_client import EmailClient
from .logging_setup import configure_logging, get_logger
from .parser import ReplyParser
from .pending import PendingStore
from .pickup_schedule import find_date_column_index
from .reply import handle_reply
from .send import run_send_flow
from .cutoff import run_cutoff_flow
from .sheets import SheetsClient
from .twilio_client import TwilioClient

configure_logging()
log = get_logger(__name__)


def lambda_handler(event: dict, context: Any) -> Any:
    if _is_scheduled_event(event):
        flow = event.get("detail", {}).get("flow")
        if flow == "send":
            return _run_send()
        if flow == "cutoff":
            return _run_cutoff()
        log.error("unknown_scheduled_flow", detail=event.get("detail"))
        return {"status": "unknown_flow"}
    if _is_api_gateway_event(event):
        return _handle_webhook(event)
    log.error("unknown_event_shape", event_keys=list(event.keys()))
    return {"status": "unknown_event"}


def _is_scheduled_event(event: dict) -> bool:
    return event.get("source") == "aws.events" or event.get("detail-type") == "Scheduled Event"


def _is_api_gateway_event(event: dict) -> bool:
    return "requestContext" in event and "http" in event.get("requestContext", {})


def _now_tz(tz_name: str) -> datetime:
    return datetime.now(tz=ZoneInfo(tz_name))


def _sunday_after(now_local: datetime) -> date:
    # Saturday 5pm local → tomorrow; cutoff Saturday ~9pm local → tomorrow
    return (now_local + timedelta(days=1)).date()


def _bootstrap_clients():
    cfg = get_config()
    secrets = cfg.load_secrets()
    sheets = SheetsClient(secrets.google_service_account, cfg.spreadsheet_id)
    twilio = TwilioClient(
        account_sid=secrets.twilio_account_sid,
        auth_token=secrets.twilio_auth_token,
        from_number=cfg.twilio_from_number,
        dry_run=cfg.dry_run,
    )
    parser = ReplyParser(anthropic_api_key=secrets.anthropic_api_key)
    email = EmailClient(
        sender=cfg.summary_email_from,
        recipients=cfg.summary_email_recipients,
        region=cfg.aws_region,
        dry_run=cfg.dry_run,
    )
    return cfg, sheets, twilio, parser, email


def _run_send() -> dict:
    cfg, sheets, twilio, _, _ = _bootstrap_clients()
    now_local = _now_tz(cfg.timezone)
    target = _sunday_after(now_local)
    result = run_send_flow(
        sheets=sheets,
        twilio=twilio,
        pickup_tab=cfg.pickup_tab_name,
        kids_info_tab=cfg.kids_info_tab_name,
        pending_tab=cfg.pending_tab_name,
        target_date=target,
        coordinator_name=cfg.coordinator_name,
        now=now_local.astimezone(timezone.utc),
    )
    log.info(
        "send_flow_complete",
        groups_sent=result.groups_sent,
        groups_skipped=result.groups_skipped,
        sms_sent=result.sms_sent,
        sms_failed=result.sms_failed,
        aborted=result.aborted,
    )
    return {"status": "ok", "groups_sent": result.groups_sent}


def _run_cutoff() -> dict:
    cfg, sheets, _, _, email = _bootstrap_clients()
    now_local = _now_tz(cfg.timezone)
    # Cutoff runs shortly after midnight UTC Sunday (= Saturday 9pm ET).
    # From Saturday local time, tomorrow is Sunday; from Sunday local, today is Sunday.
    target = now_local.date() if now_local.weekday() == 6 else _sunday_after(now_local)
    pickup_rows = sheets.read_range(f"'{cfg.pickup_tab_name}'!A1:Z1000")
    col_index = find_date_column_index(pickup_rows[0], target) if pickup_rows else None
    if col_index is None:
        log.error("cutoff_column_not_found", target=target.isoformat())
        return {"status": "column_not_found"}
    store = PendingStore(sheets, cfg.pending_tab_name)
    run_cutoff_flow(
        sheets=sheets,
        store=store,
        email=email,
        pickup_tab=cfg.pickup_tab_name,
        pickup_col_index=col_index,
        target_date=target,
        now=now_local.astimezone(timezone.utc),
    )
    return {"status": "ok"}


def _handle_webhook(event: dict) -> dict:
    cfg, sheets, twilio, parser, _ = _bootstrap_clients()

    raw_body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    params_multi = parse_qs(raw_body)
    params = {k: v[0] for k, v in params_multi.items()}

    signature = _header(event, "x-twilio-signature")
    url = _reconstruct_url(event)
    if not twilio.validate_signature(url, params, signature or ""):
        log.warning("twilio_signature_invalid")
        return {"statusCode": 403, "body": ""}

    from_phone = params.get("From", "")
    body = params.get("Body", "")

    now_local = _now_tz(cfg.timezone)
    # Reply time: the pending pickup is the upcoming Sunday. If it's Saturday
    # afternoon through just after midnight, that's "tomorrow from Saturday's frame",
    # which equals (now + 1 day).date() when we're before midnight Sunday, or
    # today's date when we're already on Sunday.
    target = now_local.date() if now_local.weekday() == 6 else _sunday_after(now_local)
    pickup_rows = sheets.read_range(f"'{cfg.pickup_tab_name}'!A1:Z1000")
    col_index = find_date_column_index(pickup_rows[0], target) if pickup_rows else None
    if col_index is None:
        log.error("reply_column_not_found", target=target.isoformat())
        return _twiml_response("")

    store = PendingStore(sheets, cfg.pending_tab_name)
    outcome = handle_reply(
        sheets=sheets,
        store=store,
        parser=parser,
        from_phone=from_phone,
        body=body,
        pickup_tab=cfg.pickup_tab_name,
        pickup_col_index=col_index,
        pickup_date=target,
        now=now_local.astimezone(timezone.utc),
    )
    log.info("reply_handled", action=outcome.action, from_phone=from_phone)
    return _twiml_response(outcome.reply_text or "")


def _header(event: dict, name: str) -> str | None:
    headers = event.get("headers") or {}
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None


def _reconstruct_url(event: dict) -> str:
    ctx = event.get("requestContext", {})
    domain = ctx.get("domainName", "")
    path = event.get("rawPath") or ctx.get("http", {}).get("path", "/sms")
    return f"https://{domain}{path}"


def _twiml_response(message_text: str) -> dict:
    if message_text:
        body = f"<Response><Message>{_escape_xml(message_text)}</Message></Response>"
    else:
        body = "<Response/>"
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/xml"},
        "body": body,
    }


def _escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/child_pickup/handler.py tests/test_handler.py
git commit -m "feat(handler): Lambda dispatch for schedule + webhook events"
```

---

## Task 16: SAM template (infrastructure as code)

**Files:**
- Create: `template.yaml`

**No unit tests for the SAM template.** Validate with `sam validate` and `sam build`.

- [ ] **Step 1: Create `template.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Child pickup confirmation app

Parameters:
  SpreadsheetId:
    Type: String
  PickupTabName:
    Type: String
    Default: 'Pickup Schedule'
  KidsInfoTabName:
    Type: String
    Default: 'All DMV KidsInfo'
  PendingTabName:
    Type: String
    Default: 'Pending Confirmations'
  TwilioFromNumber:
    Type: String
  SummaryEmailRecipients:
    Type: String
    Description: Comma-separated list
  SummaryEmailFrom:
    Type: String
  CoordinatorName:
    Type: String
    Default: 'DMV pickup coordinator'
  Timezone:
    Type: String
    Default: America/New_York
  DryRun:
    Type: String
    Default: 'false'
    AllowedValues: ['true', 'false']

Globals:
  Function:
    Runtime: python3.12
    Timeout: 60
    MemorySize: 256
    Architectures:
      - arm64

Resources:
  ChildPickupFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: child-pickup-handler
      CodeUri: src/
      Handler: child_pickup.handler.lambda_handler
      Environment:
        Variables:
          SPREADSHEET_ID: !Ref SpreadsheetId
          PICKUP_TAB_NAME: !Ref PickupTabName
          KIDS_INFO_TAB_NAME: !Ref KidsInfoTabName
          PENDING_TAB_NAME: !Ref PendingTabName
          TWILIO_FROM_NUMBER: !Ref TwilioFromNumber
          SUMMARY_EMAIL_RECIPIENTS: !Ref SummaryEmailRecipients
          SUMMARY_EMAIL_FROM: !Ref SummaryEmailFrom
          COORDINATOR_NAME: !Ref CoordinatorName
          TIMEZONE: !Ref Timezone
          DRY_RUN: !Ref DryRun
      Policies:
        - Statement:
            - Effect: Allow
              Action:
                - secretsmanager:GetSecretValue
              Resource:
                - !Sub 'arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:child-pickup/*'
            - Effect: Allow
              Action:
                - ses:SendEmail
              Resource: '*'
      Events:
        SendSchedule:
          Type: Schedule
          Properties:
            # 21:00 UTC Saturday ≈ 5pm ET (EDT); 4pm ET during EST.
            Schedule: cron(0 21 ? * SAT *)
            Input: '{"source":"aws.events","detail-type":"Scheduled Event","detail":{"flow":"send"}}'
        CutoffSchedule:
          Type: Schedule
          Properties:
            # 01:00 UTC Sunday ≈ 9pm ET Saturday (EDT); 8pm ET during EST.
            Schedule: cron(0 1 ? * SUN *)
            Input: '{"source":"aws.events","detail-type":"Scheduled Event","detail":{"flow":"cutoff"}}'
        SmsWebhook:
          Type: HttpApi
          Properties:
            Path: /sms
            Method: POST

  ErrorAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: child-pickup-errors
      MetricName: Errors
      Namespace: AWS/Lambda
      Dimensions:
        - Name: FunctionName
          Value: !Ref ChildPickupFunction
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 1
      Threshold: 0
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching

Outputs:
  WebhookUrl:
    Description: Configure this as the Twilio incoming SMS webhook (POST)
    Value: !Sub 'https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com/sms'
```

- [ ] **Step 2: Validate**

```bash
sam validate
```
Expected: "template.yaml is a valid SAM Template"

(If `sam` CLI is not installed, install from https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)

- [ ] **Step 3: Commit**

```bash
git add template.yaml
git commit -m "chore: SAM template with schedules, webhook, and alarm"
```

---

## Task 17: Package the source for Lambda

SAM expects the Lambda source laid out so `Handler: child_pickup.handler.lambda_handler` resolves. With `CodeUri: src/` and `Handler: child_pickup.handler.lambda_handler`, SAM zips `src/` — `child_pickup/` must be directly under `src/`. Already true. We also need a `src/requirements.txt` so SAM installs dependencies at build.

**Files:**
- Create: `src/requirements.txt`

- [ ] **Step 1: Create `src/requirements.txt`**

```
google-api-python-client==2.149.0
google-auth==2.35.0
twilio==9.3.5
anthropic==0.39.0
structlog==24.4.0
```

(`boto3` is pre-installed in the Lambda runtime — don't pin or ship it.)

- [ ] **Step 2: Build and verify**

```bash
sam build
```
Expected: `Build Succeeded`. Produces `.aws-sam/build/ChildPickupFunction/` with `child_pickup/` and installed deps.

- [ ] **Step 3: Commit**

```bash
git add src/requirements.txt
git commit -m "chore: Lambda dependency manifest"
```

---

## Task 18: End-to-end test suite pass

- [ ] **Step 1: Run full test suite**

```bash
pytest -v
```
Expected: all tests pass.

- [ ] **Step 2: Lint check (optional but nice)**

```bash
python -m py_compile src/child_pickup/*.py
```
Expected: no output.

- [ ] **Step 3: Commit any final fixes**

If you needed to tweak anything (imports, small bugs) during cleanup:

```bash
git add -A
git commit -m "fix: end-to-end test suite cleanup"
```

---

## Deployment checklist (manual, post-plan)

These are the once-off setup steps the operator runs after the code is merged. They are **not** plan tasks — they require human action in external systems.

- [ ] **GCP:** create project, enable Sheets API, create service account, download JSON key.
- [ ] **Google Sheet:** add a `Pending Confirmations` tab with the 12 headers listed in `models.py`. Share the spreadsheet with the service account email address (Editor).
- [ ] **Secrets Manager:** create three secrets named `child-pickup/twilio`, `child-pickup/google-service-account`, `child-pickup/anthropic`.
- [ ] **Twilio:** buy an SMS-capable US number.
- [ ] **SES:** verify sender domain/address; if in sandbox, also verify recipient addresses or request production access.
- [ ] **SAM deploy** (guided first time): `sam deploy --guided` — pin all parameters.
- [ ] **Twilio webhook:** paste the `WebhookUrl` output from the deploy into the Twilio phone number's Messaging "A message comes in" webhook (POST).
- [ ] **First real run:** `DRY_RUN=true` — inspect CloudWatch logs for intended behavior.
- [ ] **Second run:** flip to `DRY_RUN=false`, run once manually via the Lambda console, verify the sheet updates and text messages arrive.
- [ ] **Enable schedules:** they're enabled by default in the template. Confirm on the EventBridge console.

---

## Spec coverage check

Mapping spec sections to tasks:

| Spec section | Implemented by |
|---|---|
| Architecture (single Lambda dispatch) | Task 15 |
| Data model — `Child`, `Group`, `PendingConfirmation` | Task 2 |
| Data model — Pending Confirmations tab layout | Task 2 (models), Task 8 (I/O) |
| KidsInfo tab parsing | Task 6 |
| Pickup Schedule reading + grouping | Task 7 |
| Send flow | Task 12 |
| SMS body composition | Task 9 |
| Twilio send + signature validation | Task 9 |
| Reply flow incl. regex + LLM fallback | Task 10 (parser), Task 13 (orchestration) |
| Cutoff flow | Task 14 |
| Summary email via SES | Task 11 |
| Config + Secrets Manager | Task 3 |
| Structured logging | Task 4 |
| SheetsClient wrapper | Task 5 |
| Dry-run support across boundary clients | Tasks 9, 11 (Twilio, Email); config flag in Task 3 |
| SAM infrastructure (EventBridge, HttpApi, alarm) | Task 16 |
| Lambda packaging | Task 17 |
| Full test suite | Task 18 |
