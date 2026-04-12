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
