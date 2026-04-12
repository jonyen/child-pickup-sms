from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Optional

from google import genai

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
    def __init__(self, gemini_api_key: str, model: str = "gemini-2.0-flash"):
        self._model = model
        self._client = genai.Client(api_key=gemini_api_key)

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
            resp = self._client.models.generate_content(
                model=self._model,
                contents=user_msg,
                config=genai.types.GenerateContentConfig(
                    system_instruction=LLM_SYSTEM_PROMPT,
                    max_output_tokens=128,
                ),
            )
            text = resp.text.strip()
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
