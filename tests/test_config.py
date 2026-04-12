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
        {"SecretString": json.dumps({"client_id": "cid", "client_secret": "csec", "refresh_token": "rtok"})},
        {"SecretString": json.dumps({"api_key": "sk-ant-1"})},
    ]
    secrets = cfg.load_secrets()
    assert secrets.twilio_account_sid == "AC1"
    assert secrets.twilio_auth_token == "TOK"
    assert secrets.google_oauth["refresh_token"] == "rtok"
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
