from datetime import date
from unittest.mock import MagicMock, patch
from child_pickup.email_client import EmailClient, SummaryData, GroupOutcome


@patch("child_pickup.email_client.boto3")
def test_send_summary_calls_ses(mock_boto3):
    mock_ses = MagicMock()
    mock_boto3.client.return_value = mock_ses
    client = EmailClient(
        sender="pickup@dmv.org",
        recipients=["a@b.com", "c@d.com"],
        region="us-east-1",
        dry_run=False,
    )
    data = SummaryData(
        pickup_date=date(2026, 4, 12),
        confirmed=[GroupOutcome("Hanseul or Deandra", ["Caden Shim"], None)],
        changed=[GroupOutcome("Grandma Linda", ["Estelle Chow"], "Jenny or Alan")],
        absent=[GroupOutcome("Shara", ["Bobby Chow"])],
        no_response=[GroupOutcome("Shara", ["Alice"], None, parent_contacts=[("Jen", "+15551110000")])],
        send_errors=["no phones for Ghost Kid"],
    )
    client.send_summary(data)
    mock_ses.send_email.assert_called_once()
    kwargs = mock_ses.send_email.call_args.kwargs
    assert kwargs["Source"] == "pickup@dmv.org"
    assert set(kwargs["Destination"]["ToAddresses"]) == {"a@b.com", "c@d.com"}
    body = kwargs["Message"]["Body"]["Text"]["Data"]
    assert "2026-04-12" in body
    assert "Caden Shim" in body
    assert "Grandma Linda" in body
    assert "Shara" in body
    assert "+15551110000" in body
    assert "Ghost Kid" in body


@patch("child_pickup.email_client.boto3")
def test_send_summary_dry_run_skips(mock_boto3):
    client = EmailClient(
        sender="pickup@dmv.org",
        recipients=["a@b.com"],
        region="us-east-1",
        dry_run=True,
    )
    data = SummaryData(pickup_date=date(2026, 4, 12), confirmed=[], changed=[],
                       absent=[], no_response=[], send_errors=[])
    client.send_summary(data)
    mock_boto3.client.assert_not_called()
