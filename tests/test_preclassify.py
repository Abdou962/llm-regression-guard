"""Tests for src/preclassify.py — pre-classification of fetched emails."""

from unittest.mock import patch

import pytest

from src.preclassify import _dummy_classify, _is_real_mode, preclassify_emails


# -- Dummy classifier -------------------------------------------------------


class TestDummyClassify:
    def test_account_keyword(self):
        r = _dummy_classify("I can't login to my account")
        assert r["category"] == "account"

    def test_billing_keyword(self):
        r = _dummy_classify("Why was I charged twice?")
        assert r["category"] == "billing"

    def test_technical_keyword(self):
        r = _dummy_classify("The app keeps crashing")
        assert r["category"] == "technical"

    def test_feature_request_keyword(self):
        r = _dummy_classify("Can you add dark mode?")
        assert r["category"] == "feature_request"

    def test_security_keyword(self):
        r = _dummy_classify("I got a phishing email from your domain")
        assert r["category"] == "security"

    def test_general_fallback(self):
        r = _dummy_classify("Hello, how are you?")
        assert r["category"] == "general"

    def test_empty_input(self):
        r = _dummy_classify("")
        assert r["category"] == "general"

    def test_none_input(self):
        r = _dummy_classify(None)
        assert r["category"] == "general"


# -- Mode detection ----------------------------------------------------------


class TestIsRealMode:
    def test_no_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert _is_real_mode() is False

    def test_placeholder_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-<your-key>")
        assert _is_real_mode() is False

    def test_valid_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-key-123")
        assert _is_real_mode() is True


# -- preclassify_emails (dummy mode) ----------------------------------------


class TestPreclassifyEmails:
    @pytest.fixture()
    def sample_emails(self):
        return [
            {
                "message_id": "<1@test>",
                "sender": "user@test.com",
                "subject": "Can't login",
                "body": "I forgot my password and can't login.",
                "received_at": "2026-04-18T10:00:00",
            },
            {
                "message_id": "<2@test>",
                "sender": "boss@corp.com",
                "subject": "Invoice question",
                "body": "I was charged $200 instead of $20.",
                "received_at": "2026-04-18T11:00:00",
            },
            {
                "message_id": "<3@test>",
                "sender": "dev@startup.io",
                "subject": "Hello",
                "body": "Just wanted to say hi!",
                "received_at": "2026-04-18T12:00:00",
            },
        ]

    def test_returns_proposals_for_all_emails(self, monkeypatch, sample_emails):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        proposals = preclassify_emails(sample_emails)
        assert len(proposals) == 3

    def test_proposals_have_required_keys(self, monkeypatch, sample_emails):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        proposals = preclassify_emails(sample_emails)
        for p in proposals:
            assert "proposed_category" in p
            assert "proposed_summary" in p
            assert "mode" in p
            assert "latency" in p
            # Original email keys preserved
            assert "message_id" in p
            assert "sender" in p
            assert "body" in p

    def test_classifies_correctly_in_dummy_mode(self, monkeypatch, sample_emails):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        proposals = preclassify_emails(sample_emails)
        assert proposals[0]["proposed_category"] == "account"  # "login" keyword
        assert proposals[1]["proposed_category"] == "billing"  # "charged" keyword
        assert proposals[2]["proposed_category"] == "general"  # no keyword match

    def test_mode_is_dummy(self, monkeypatch, sample_emails):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        proposals = preclassify_emails(sample_emails)
        assert "dummy" in proposals[0]["mode"]

    def test_latency_is_positive(self, monkeypatch, sample_emails):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        proposals = preclassify_emails(sample_emails)
        for p in proposals:
            assert p["latency"] >= 0

    def test_empty_email_list(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        proposals = preclassify_emails([])
        assert proposals == []

    def test_preserves_original_email_data(self, monkeypatch, sample_emails):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        proposals = preclassify_emails(sample_emails)
        assert proposals[0]["sender"] == "user@test.com"
        assert proposals[1]["subject"] == "Invoice question"

    @patch("src.preclassify._is_real_mode", return_value=False)
    @patch("src.preclassify._dummy_classify", side_effect=Exception("boom"))
    def test_handles_classification_error(self, _mock_classify, _mock_mode, sample_emails):
        proposals = preclassify_emails(sample_emails)
        # Should fall back to "general" on error
        for p in proposals:
            assert p["proposed_category"] == "general"
            assert "boom" in p["proposed_summary"]
