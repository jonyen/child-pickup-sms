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
        self._api_key = anthropic_api_key
        self._model = model
        self._client = None  # lazy init to keep regex-only tests from touching the SDK

    def _get_client(self):
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

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
            resp = self._get_client().messages.create(
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
