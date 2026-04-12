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
    sheets = SheetsClient(secrets.google_oauth, cfg.spreadsheet_id)
    twilio = TwilioClient(
        account_sid=secrets.twilio_account_sid,
        auth_token=secrets.twilio_auth_token,
        from_number=cfg.twilio_from_number,
        dry_run=cfg.dry_run,
    )
    parser = ReplyParser(gemini_api_key=secrets.gemini_api_key)
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
        target_date=target,
        coordinator_name=cfg.coordinator_name,
        now=now_local.astimezone(timezone.utc),
    )
    log.info(
        "send_flow_complete",
        groups_sent=result.groups_sent,
        sms_sent=result.sms_sent,
        sms_failed=result.sms_failed,
        aborted=result.aborted,
    )
    return {"status": "ok", "groups_sent": result.groups_sent}


def _run_cutoff() -> dict:
    cfg, sheets, _, _, email = _bootstrap_clients()
    now_local = _now_tz(cfg.timezone)
    target = now_local.date() if now_local.weekday() == 6 else _sunday_after(now_local)
    pickup_rows = sheets.read_range(f"'{cfg.pickup_tab_name}'!A1:Z1000")
    col_index = find_date_column_index(pickup_rows[0], target) if pickup_rows else None
    if col_index is None:
        log.error("cutoff_column_not_found", target=target.isoformat())
        return {"status": "column_not_found"}
    run_cutoff_flow(
        sheets=sheets,
        email=email,
        pickup_tab=cfg.pickup_tab_name,
        kids_info_tab=cfg.kids_info_tab_name,
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
    target = now_local.date() if now_local.weekday() == 6 else _sunday_after(now_local)
    pickup_rows = sheets.read_range(f"'{cfg.pickup_tab_name}'!A1:Z1000")
    col_index = find_date_column_index(pickup_rows[0], target) if pickup_rows else None
    if col_index is None:
        log.error("reply_column_not_found", target=target.isoformat())
        return _twiml_response("")

    outcome = handle_reply(
        sheets=sheets,
        parser=parser,
        from_phone=from_phone,
        body=body,
        pickup_tab=cfg.pickup_tab_name,
        kids_info_tab=cfg.kids_info_tab_name,
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
