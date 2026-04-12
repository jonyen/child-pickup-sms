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
