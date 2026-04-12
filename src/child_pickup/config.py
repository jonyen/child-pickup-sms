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
    google_oauth: dict  # {client_id, client_secret, refresh_token}
    anthropic_api_key: str


@dataclass
class Config:
    spreadsheet_id: str
    pickup_tab_name: str
    kids_info_tab_name: str
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
            sm.get_secret_value(SecretId="child-pickup/google-oauth")["SecretString"]
        )
        anthropic = json.loads(
            sm.get_secret_value(SecretId="child-pickup/anthropic")["SecretString"]
        )
        return Secrets(
            twilio_account_sid=twilio["account_sid"],
            twilio_auth_token=twilio["auth_token"],
            google_oauth=google,
            anthropic_api_key=anthropic["api_key"],
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config.from_env()
