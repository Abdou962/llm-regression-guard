"""
Slack alerting module — sends formatted alerts via webhook.
"""
import os

import requests
from datetime import datetime

# Load .env from project root
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(os.path.abspath(_env_path))
except ImportError:
    pass

from Scripts.slack_utils import get_status_color, get_status_emoji


def get_slack_webhook() -> str | None:
    """Retrieve Slack webhook URL from environment."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("[WARN] SLACK_WEBHOOK_URL not set in .env or environment.")
        return None
    return webhook_url


def send_simple_alert(message_text: str, status: str = "pass") -> bool:
    """
    Send a simple Slack alert with color-coded status.

    Args:
        message_text: The alert message body.
        status: One of 'pass', 'warn', 'fail'.

    Returns:
        True if sent successfully, False otherwise.
    """
    webhook_url = get_slack_webhook()
    if not webhook_url:
        return False

    color = get_status_color(status)
    emoji = get_status_emoji(status)
    payload = {
        "attachments": [
            {
                "color": color,
                "text": f"{emoji} {message_text}",
                "footer": "LLM Regression Pipeline",
                "ts": int(datetime.now().timestamp()),
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.Timeout:
        print("[ERROR] Slack webhook timed out.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send Slack alert: {e}")
        return False