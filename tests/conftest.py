import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_sheets_client():
    return MagicMock()


@pytest.fixture
def mock_twilio_client():
    return MagicMock()


@pytest.fixture
def mock_claude_client():
    return MagicMock()


@pytest.fixture
def mock_email_client():
    return MagicMock()
