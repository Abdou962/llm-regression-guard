"""
Fetch emails from a mailbox via IMAP.

Grabs unread messages from Gmail (or any IMAP server),
strips HTML junk, and returns clean dicts ready to feed
into the classification pipeline.
"""

import contextlib
import email
import html
import imaplib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any


@dataclass
class IMAPConfig:
    """Connection settings — loaded from env vars via from_env()."""

    server: str
    port: int
    email_addr: str
    password: str
    folder: str = "INBOX"
    use_ssl: bool = True

    @classmethod
    def from_env(cls) -> "IMAPConfig":
        """Read IMAP_* env vars and build a config. Raises if required ones are missing."""
        server = os.getenv("IMAP_SERVER", "")
        email_addr = os.getenv("IMAP_EMAIL", "")
        password = os.getenv("IMAP_PASSWORD", "")

        # Fail early with a clear message instead of cryptic IMAP errors later
        if not server:
            raise ValueError("IMAP_SERVER is not set")
        if not email_addr:
            raise ValueError("IMAP_EMAIL is not set")
        if not password:
            raise ValueError("IMAP_PASSWORD is not set")

        return cls(
            server=server,
            port=int(os.getenv("IMAP_PORT", "993")),
            email_addr=email_addr,
            password=password,
            folder=os.getenv("IMAP_FOLDER", "INBOX"),
            use_ssl=os.getenv("IMAP_USE_SSL", "true").lower() == "true",
        )


# -- HTML to plain text ------------------------------------------------------


class _HTMLTextExtractor(HTMLParser):
    """Quick and dirty HTML stripper — just grabs the visible text."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def strip_html(raw_html: str) -> str:
    """Turn HTML into readable text (decode entities, collapse whitespace)."""
    extractor = _HTMLTextExtractor()
    extractor.feed(html.unescape(raw_html))
    text = extractor.get_text()
    return re.sub(r"\s+", " ", text).strip()


# -- Internal helpers ---------------------------------------------------------


def _decode_header(value: str | None) -> str:
    """Decode RFC-2047 encoded header (handles =?utf-8?B?...?= etc.)."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for fragment, charset in parts:
        if isinstance(fragment, bytes):
            decoded.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(fragment)
    return " ".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    """Pull the text body out of a MIME message. Prefers plain text over HTML."""
    # Simple single-part message
    if not msg.is_multipart():
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                return strip_html(text)
            return text.strip()
        return ""

    # Multipart: walk through all parts, collect plain and html
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in msg.walk():
        content_type = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if content_type == "text/plain":
            plain_parts.append(text.strip())
        elif content_type == "text/html":
            html_parts.append(strip_html(text))

    # Prefer plain text when available
    if plain_parts:
        return "\n".join(plain_parts)
    if html_parts:
        return "\n".join(html_parts)
    return ""


def _parse_date(msg: email.message.Message) -> str:
    """Get the Date header as ISO string. Falls back to now() if unparseable."""
    date_str = msg.get("Date")
    if date_str:
        try:
            return parsedate_to_datetime(date_str).isoformat(timespec="seconds")
        except (ValueError, TypeError):
            pass
    return datetime.now().isoformat(timespec="seconds")


# -- Public API ---------------------------------------------------------------


def connect_imap(config: IMAPConfig) -> imaplib.IMAP4 | imaplib.IMAP4_SSL:
    """Open an IMAP connection and log in."""
    if config.use_ssl:
        conn = imaplib.IMAP4_SSL(config.server, config.port)
    else:
        conn = imaplib.IMAP4(config.server, config.port)
    conn.login(config.email_addr, config.password)
    return conn


def fetch_unread_emails(
    config: IMAPConfig,
    max_emails: int = 50,
    mark_as_read: bool = False,
) -> list[dict[str, Any]]:
    """
    Grab unread emails from the mailbox.

    Returns a list of dicts: {message_id, sender, subject, body, received_at}.
    By default reads in readonly mode — set mark_as_read=True to flag them SEEN.
    """
    conn = connect_imap(config)
    try:
        conn.select(config.folder, readonly=not mark_as_read)
        _status, data = conn.search(None, "UNSEEN")
        if not data or not data[0]:
            return []

        # Take the N most recent (last in the list = newest)
        msg_ids = data[0].split()[-max_emails:]
        results: list[dict[str, Any]] = []

        for mid in msg_ids:
            _status, msg_data = conn.fetch(mid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            body = _extract_body(msg)
            if not body:
                continue  # Skip empty emails, nothing to classify

            results.append(
                {
                    "message_id": msg.get("Message-ID", f"no-id-{mid.decode()}"),
                    "sender": _decode_header(msg.get("From")),
                    "subject": _decode_header(msg.get("Subject")),
                    "body": body[:5000],  # Truncate huge emails
                    "received_at": _parse_date(msg),
                }
            )

            if mark_as_read:
                conn.store(mid, "+FLAGS", "\\Seen")

        return results
    finally:
        with contextlib.suppress(Exception):
            conn.close()
        conn.logout()
