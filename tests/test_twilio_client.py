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
