import json
from unittest.mock import MagicMock, patch
from child_pickup.parser import ReplyParser, ParseResult


def test_regex_yes_variants_return_confirm():
    with patch("child_pickup.parser.genai.Client"):
        parser = ReplyParser(gemini_api_key="test-key")
    for body in ["YES", "yes", "Y", "Yep", "yeah", " YUP ", "OK", "okay.", "Sure!"]:
        r = parser.parse(body, ongoing_person="Hanseul or Deandra",
                         children_names=["Caden Shim"])
        assert r.action == "confirm", f"{body} should confirm"
        assert r.new_pickup_person is None


def test_regex_no_variants_return_absent():
    with patch("child_pickup.parser.genai.Client"):
        parser = ReplyParser(gemini_api_key="test-key")
    for body in ["NO", "no", "Not coming", "not today", "Absent", " skip ", "Can't come!"]:
        r = parser.parse(body, ongoing_person="Hanseul or Deandra",
                         children_names=["Caden Shim"])
        assert r.action == "absent", f"{body} should be absent"
        assert r.new_pickup_person is None


@patch("child_pickup.parser.genai.Client")
def test_llm_absent_response(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps(
            {"action": "absent", "new_pickup_person": None}
        )
    )
    parser = ReplyParser(gemini_api_key="test-key")
    r = parser.parse(
        "she's sick today so we won't be there",
        ongoing_person="Hanseul or Deandra",
        children_names=["Caden Shim"],
    )
    assert r.action == "absent"
    assert r.new_pickup_person is None


@patch("child_pickup.parser.genai.Client")
def test_llm_fallback_on_non_matching_reply(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps(
            {"action": "change", "new_pickup_person": "Grandma Linda"}
        )
    )
    parser = ReplyParser(gemini_api_key="test-key")
    r = parser.parse(
        "actually my mom Linda is grabbing him",
        ongoing_person="Hanseul or Deandra",
        children_names=["Caden Shim"],
    )
    assert r.action == "change"
    assert r.new_pickup_person == "Grandma Linda"


@patch("child_pickup.parser.genai.Client")
def test_llm_ambiguous_response(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps(
            {"action": "ambiguous", "new_pickup_person": None}
        )
    )
    parser = ReplyParser(gemini_api_key="test-key")
    r = parser.parse("hmm", ongoing_person="Shara", children_names=["Estelle Chow"])
    assert r.action == "ambiguous"


@patch("child_pickup.parser.genai.Client")
def test_llm_malformed_json_becomes_ambiguous(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.return_value = MagicMock(
        text="not json at all"
    )
    parser = ReplyParser(gemini_api_key="test-key")
    r = parser.parse("?", ongoing_person="Shara", children_names=["Estelle Chow"])
    assert r.action == "ambiguous"
