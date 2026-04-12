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
