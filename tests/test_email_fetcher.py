"""Tests for src/email_fetcher.py — IMAP email fetching module."""

import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

from src.email_fetcher import (
    IMAPConfig,
    _decode_header,
    _extract_body,
    _parse_date,
    connect_imap,
    fetch_unread_emails,
    strip_html,
)

# ---------------------------------------------------------------------------
# IMAPConfig
# ---------------------------------------------------------------------------


class TestIMAPConfig:
    def test_from_env_ok(self, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.example.com")
        monkeypatch.setenv("IMAP_PORT", "993")
        monkeypatch.setenv("IMAP_EMAIL", "a@b.com")
        monkeypatch.setenv("IMAP_PASSWORD", "secret")
        monkeypatch.setenv("IMAP_FOLDER", "INBOX")
        monkeypatch.setenv("IMAP_USE_SSL", "true")
        cfg = IMAPConfig.from_env()
        assert cfg.server == "imap.example.com"
        assert cfg.port == 993
        assert cfg.email_addr == "a@b.com"
        assert cfg.password == "secret"
        assert cfg.use_ssl is True

    def test_from_env_missing_server(self, monkeypatch):
        monkeypatch.delenv("IMAP_SERVER", raising=False)
        with pytest.raises(ValueError, match="IMAP_SERVER"):
            IMAPConfig.from_env()

    def test_from_env_missing_email(self, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.example.com")
        monkeypatch.delenv("IMAP_EMAIL", raising=False)
        with pytest.raises(ValueError, match="IMAP_EMAIL"):
            IMAPConfig.from_env()

    def test_from_env_missing_password(self, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.example.com")
        monkeypatch.setenv("IMAP_EMAIL", "a@b.com")
        monkeypatch.delenv("IMAP_PASSWORD", raising=False)
        with pytest.raises(ValueError, match="IMAP_PASSWORD"):
            IMAPConfig.from_env()

    def test_defaults(self, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.example.com")
        monkeypatch.setenv("IMAP_EMAIL", "a@b.com")
        monkeypatch.setenv("IMAP_PASSWORD", "secret")
        monkeypatch.delenv("IMAP_PORT", raising=False)
        monkeypatch.delenv("IMAP_FOLDER", raising=False)
        monkeypatch.delenv("IMAP_USE_SSL", raising=False)
        cfg = IMAPConfig.from_env()
        assert cfg.port == 993
        assert cfg.folder == "INBOX"
        assert cfg.use_ssl is True

    def test_ssl_false(self, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.example.com")
        monkeypatch.setenv("IMAP_EMAIL", "a@b.com")
        monkeypatch.setenv("IMAP_PASSWORD", "secret")
        monkeypatch.setenv("IMAP_USE_SSL", "false")
        cfg = IMAPConfig.from_env()
        assert cfg.use_ssl is False


# ---------------------------------------------------------------------------
# strip_html
# ---------------------------------------------------------------------------


class TestStripHtml:
    def test_basic_html(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_entities(self):
        assert strip_html("&amp; &lt; &gt;") == "& < >"

    def test_plain_text_passthrough(self):
        assert strip_html("just text") == "just text"

    def test_collapses_whitespace(self):
        assert strip_html("<p>  hello   world  </p>") == "hello world"


# ---------------------------------------------------------------------------
# _decode_header
# ---------------------------------------------------------------------------


class TestDecodeHeader:
    def test_plain(self):
        assert _decode_header("John Doe") == "John Doe"

    def test_none(self):
        assert _decode_header(None) == ""

    def test_encoded_utf8(self):
        encoded = "=?utf-8?B?SsOpcsO0bWU=?="
        result = _decode_header(encoded)
        assert "rôme" in result


# ---------------------------------------------------------------------------
# _extract_body
# ---------------------------------------------------------------------------


class TestExtractBody:
    def test_plain_text_message(self):
        msg = MIMEText("Hello world", "plain")
        assert _extract_body(msg) == "Hello world"

    def test_html_message(self):
        msg = MIMEText("<p>Hello</p>", "html")
        assert "Hello" in _extract_body(msg)

    def test_multipart_prefers_plain(self):
        multi = MIMEMultipart("alternative")
        multi.attach(MIMEText("Plain text", "plain"))
        multi.attach(MIMEText("<p>HTML</p>", "html"))
        assert _extract_body(multi) == "Plain text"

    def test_multipart_falls_back_to_html(self):
        multi = MIMEMultipart("alternative")
        multi.attach(MIMEText("<p>HTML only</p>", "html"))
        assert "HTML only" in _extract_body(multi)

    def test_empty_payload(self):
        msg = email.message.Message()
        msg.set_payload("")
        assert _extract_body(msg) == ""


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_valid_date(self):
        msg = email.message.Message()
        msg["Date"] = "Mon, 14 Apr 2026 10:30:00 +0000"
        result = _parse_date(msg)
        assert "2026-04-14" in result

    def test_missing_date(self):
        msg = email.message.Message()
        result = _parse_date(msg)
        # Should return current time ISO string
        assert "T" in result

    def test_invalid_date(self):
        msg = email.message.Message()
        msg["Date"] = "not-a-date"
        result = _parse_date(msg)
        assert "T" in result


# ---------------------------------------------------------------------------
# connect_imap
# ---------------------------------------------------------------------------


class TestConnectImap:
    @patch("src.email_fetcher.imaplib.IMAP4_SSL")
    def test_ssl_connection(self, mock_ssl):
        config = IMAPConfig("imap.example.com", 993, "a@b.com", "pw", use_ssl=True)
        connect_imap(config)
        mock_ssl.assert_called_once_with("imap.example.com", 993)
        mock_ssl.return_value.login.assert_called_once_with("a@b.com", "pw")

    @patch("src.email_fetcher.imaplib.IMAP4")
    def test_plain_connection(self, mock_imap):
        config = IMAPConfig("imap.example.com", 143, "a@b.com", "pw", use_ssl=False)
        connect_imap(config)
        mock_imap.assert_called_once_with("imap.example.com", 143)


# ---------------------------------------------------------------------------
# fetch_unread_emails
# ---------------------------------------------------------------------------


class TestFetchUnreadEmails:
    def _make_raw_email(self, subject="Test", body="Hello", sender="a@b.com"):
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["Message-ID"] = f"<test-{subject}@example.com>"
        msg["Date"] = "Mon, 14 Apr 2026 10:00:00 +0000"
        return msg.as_bytes()

    @patch("src.email_fetcher.connect_imap")
    def test_fetches_emails(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b"1 2"])
        mock_conn.fetch.side_effect = [
            ("OK", [(b"1", self._make_raw_email("Sub1", "Body1"))]),
            ("OK", [(b"2", self._make_raw_email("Sub2", "Body2"))]),
        ]
        config = IMAPConfig("imap.example.com", 993, "a@b.com", "pw")
        results = fetch_unread_emails(config, max_emails=10)
        assert len(results) == 2
        assert results[0]["subject"] == "Sub1"
        assert results[0]["body"] == "Body1"
        assert results[1]["subject"] == "Sub2"

    @patch("src.email_fetcher.connect_imap")
    def test_empty_inbox(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b""])
        config = IMAPConfig("imap.example.com", 993, "a@b.com", "pw")
        results = fetch_unread_emails(config)
        assert results == []

    @patch("src.email_fetcher.connect_imap")
    def test_max_emails_limit(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b"1 2 3 4 5"])
        mock_conn.fetch.side_effect = [
            ("OK", [(b"4", self._make_raw_email("S4", "B4"))]),
            ("OK", [(b"5", self._make_raw_email("S5", "B5"))]),
        ]
        config = IMAPConfig("imap.example.com", 993, "a@b.com", "pw")
        results = fetch_unread_emails(config, max_emails=2)
        # Should only fetch last 2 (most recent)
        assert len(results) == 2

    @patch("src.email_fetcher.connect_imap")
    def test_mark_as_read(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(b"1", self._make_raw_email())])
        config = IMAPConfig("imap.example.com", 993, "a@b.com", "pw")
        fetch_unread_emails(config, mark_as_read=True)
        mock_conn.select.assert_called_once_with("INBOX", readonly=False)
        mock_conn.store.assert_called_once_with(b"1", "+FLAGS", "\\Seen")

    @patch("src.email_fetcher.connect_imap")
    def test_readonly_by_default(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b""])
        config = IMAPConfig("imap.example.com", 993, "a@b.com", "pw")
        fetch_unread_emails(config)
        mock_conn.select.assert_called_once_with("INBOX", readonly=True)

    @patch("src.email_fetcher.connect_imap")
    def test_skips_empty_body(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b"1"])
        empty_msg = MIMEText("", "plain")
        empty_msg["Subject"] = "Empty"
        empty_msg["From"] = "a@b.com"
        empty_msg["Message-ID"] = "<empty@test>"
        empty_msg["Date"] = "Mon, 14 Apr 2026 10:00:00 +0000"
        mock_conn.fetch.return_value = ("OK", [(b"1", empty_msg.as_bytes())])
        config = IMAPConfig("imap.example.com", 993, "a@b.com", "pw")
        results = fetch_unread_emails(config)
        assert len(results) == 0

    @patch("src.email_fetcher.connect_imap")
    def test_body_capped_at_5000(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b"1"])
        long_body = "x" * 10000
        mock_conn.fetch.return_value = ("OK", [(b"1", self._make_raw_email(body=long_body))])
        config = IMAPConfig("imap.example.com", 993, "a@b.com", "pw")
        results = fetch_unread_emails(config)
        assert len(results[0]["body"]) == 5000
