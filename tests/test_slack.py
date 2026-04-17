"""
Unit tests for Slack alerting modules — slack_utils and slack_alerter.
"""

from unittest.mock import MagicMock, patch

from Scripts.slack_utils import get_status_color, get_status_emoji

# --- slack_utils ---


class TestGetStatusColor:
    def test_pass(self):
        assert get_status_color("pass") == "#28a745"

    def test_warn(self):
        assert get_status_color("warn") == "#ffc107"

    def test_fail(self):
        assert get_status_color("fail") == "#dc3545"

    def test_unknown_returns_default(self):
        assert get_status_color("other") == "#6c757d"


class TestGetStatusEmoji:
    def test_pass(self):
        assert get_status_emoji("pass") == "✅"

    def test_warn(self):
        assert get_status_emoji("warn") == "⚠️"

    def test_fail(self):
        assert get_status_emoji("fail") == "🔴"

    def test_unknown_returns_default(self):
        result = get_status_emoji("other")
        assert "\u2139" in result


# --- slack_alerter ---


class TestGetSlackWebhook:
    def test_returns_url_when_set(self):
        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
            from Scripts.slack_alerter import get_slack_webhook

            assert get_slack_webhook() == "https://hooks.slack.com/test"

    def test_returns_none_when_unset(self):
        with patch.dict("os.environ", {}, clear=True):
            from Scripts.slack_alerter import get_slack_webhook

            assert get_slack_webhook() is None


class TestSendSimpleAlert:
    def test_returns_false_when_no_webhook(self):
        with patch.dict("os.environ", {}, clear=True):
            from Scripts.slack_alerter import send_simple_alert

            assert send_simple_alert("test message") is False

    def test_sends_successfully(self):
        with (
            patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}),
            patch("Scripts.slack_alerter.requests.post") as mock_post,
        ):
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            from Scripts.slack_alerter import send_simple_alert

            result = send_simple_alert("Pipeline passed!", status="pass")

            assert result is True
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert "✅" in payload["attachments"][0]["text"]

    def test_returns_false_on_timeout(self):
        import requests

        with (
            patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}),
            patch("Scripts.slack_alerter.requests.post", side_effect=requests.exceptions.Timeout),
        ):
            from Scripts.slack_alerter import send_simple_alert

            assert send_simple_alert("test") is False

    def test_returns_false_on_request_error(self):
        import requests

        with (
            patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}),
            patch(
                "Scripts.slack_alerter.requests.post",
                side_effect=requests.exceptions.ConnectionError("connection failed"),
            ),
        ):
            from Scripts.slack_alerter import send_simple_alert

            assert send_simple_alert("test") is False
