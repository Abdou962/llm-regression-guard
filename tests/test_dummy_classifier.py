"""
Unit tests for the dummy classifier in run_model_on_golden.
"""

import pytest

from src.run_model_on_golden import _dummy_classify


@pytest.mark.parametrize(
    "email,expected_category",
    [
        ("I can't log in to my account.", "account"),
        ("My password is not working.", "account"),
        ("Account locked after too many attempts.", "account"),
        ("Why was I charged twice?", "billing"),
        ("I need a refund for my invoice.", "billing"),
        ("Can I see my payment history?", "billing"),
        ("The app crashes when I click send.", "technical"),
        ("I found a bug in the upload feature.", "technical"),
        ("Error 500 when loading the page.", "technical"),
        ("Can you add dark mode?", "feature_request"),
        ("I'd love a CSV export feature.", "feature_request"),
        ("I got a phishing email from your domain.", "security"),
        ("There's a security vulnerability in your system.", "security"),
        ("What are your business hours?", "general"),
        ("Hello, I have a question.", "general"),
    ],
)
def test_dummy_classify_categories(email, expected_category):
    result = _dummy_classify(email)
    assert result["category"] == expected_category
    assert "summary" in result
    assert len(result["summary"]) > 0


def test_dummy_classify_empty_input():
    result = _dummy_classify("")
    assert result["category"] == "general"


def test_dummy_classify_none_input():
    result = _dummy_classify(None)
    assert result["category"] == "general"


def test_dummy_classify_case_insensitive():
    """Classifier should handle mixed case input."""
    result = _dummy_classify("MY ACCOUNT IS LOCKED")
    assert result["category"] == "account"


def test_dummy_classify_returns_dict_with_required_keys():
    result = _dummy_classify("Some email text")
    assert "category" in result
    assert "summary" in result
