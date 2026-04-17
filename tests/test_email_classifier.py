"""
Unit tests for the email classifier.
Uses mocking to avoid calling the real Anthropic API.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.email_classifier import (
    EmailClassification,
    _parse_classification,
    classify_email,
    load_prompt_config,
)

# --- Helpers ---

# NOTE: dummy_prompt_config fixture is provided by conftest.py


def _mock_anthropic_response(category: str, summary: str):
    """Create a mock Anthropic API response."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock()]
    mock_message.content[0].text = json.dumps({"category": category, "summary": summary})
    return mock_message


# --- Parser tests ---


class TestParseClassification:
    def test_valid_json(self):
        result = _parse_classification('{"category": "billing", "summary": "Billing issue."}')
        assert result["category"] == "billing"
        assert result["summary"] == "Billing issue."

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"category": "technical", "summary": "App crash."}\n```'
        result = _parse_classification(raw)
        assert result["category"] == "technical"

    def test_json_with_extra_text(self):
        raw = 'Here is the result: {"category": "account", "summary": "Cannot login."} Done.'
        result = _parse_classification(raw)
        assert result["category"] == "account"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_classification("This is not JSON at all")


# --- Classifier tests (mocked API) ---


@pytest.mark.parametrize(
    "email,expected_category,expected_summary",
    [
        ("I can't log in to my account.", "account", "User cannot access their account."),
        ("My bill is wrong.", "billing", "Incorrect billing reported."),
        ("The app crashes when I click send.", "technical", "App crashes on send action."),
        ("What are your business hours?", "general", "Customer asks about hours."),
        ("Can you add dark mode?", "feature_request", "User requests dark mode."),
        ("I got a phishing email from you.", "security", "Phishing report."),
    ],
)
def test_classify_email_with_mock(email, expected_category, expected_summary, dummy_prompt_config):
    """Test classification with mocked API responses."""
    mock_response = _mock_anthropic_response(expected_category, expected_summary)

    with patch("src.email_classifier.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        result = classify_email(email, dummy_prompt_config, "fake-key")

        assert isinstance(result, EmailClassification)
        assert result.category == expected_category
        assert len(result.summary) > 0
        mock_client.messages.create.assert_called_once()


def test_classify_email_retry_on_failure(dummy_prompt_config):
    """Test that the classifier retries on transient failures."""
    mock_success = _mock_anthropic_response("billing", "Billing issue.")

    with patch("src.email_classifier.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        # First call fails, second succeeds
        mock_client.messages.create.side_effect = [
            Exception("Transient API error"),
            mock_success,
        ]

        result = classify_email(
            "My bill is wrong.",
            dummy_prompt_config,
            "fake-key",
            max_retries=2,
        )
        assert result.category == "billing"
        assert mock_client.messages.create.call_count == 2


# --- Prompt loading tests ---


def test_load_prompt_config():
    """Test loading the real prompt YAML file."""
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "v1_billing_classifier.yaml")
    if os.path.exists(prompt_path):
        config = load_prompt_config(prompt_path)
        assert config.version == "1.0"
        assert len(config.examples) >= 4
        assert "classify" in config.system_prompt.lower() or "category" in config.system_prompt.lower()
