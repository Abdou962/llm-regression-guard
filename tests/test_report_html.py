"""
Unit tests for report_html — HTML generation, XSS escaping, trend chart, edge cases.
"""

import pytest

from src.report_html import _esc, generate_html_report


class TestEsc:
    def test_escapes_html_tags(self):
        assert "&lt;script&gt;" in _esc("<script>")

    def test_escapes_quotes(self):
        assert "&quot;" in _esc('"hello"')

    def test_escapes_ampersand(self):
        assert "&amp;" in _esc("a & b")

    def test_handles_non_string(self):
        assert _esc(42) == "42"

    def test_handles_none(self):
        assert _esc(None) == "None"


# --- Fixtures ---


@pytest.fixture
def minimal_diff_data():
    return {
        "global_pass_rate_prev": 0.90,
        "global_pass_rate_curr": 0.925,
        "delta": 0.025,
        "flag": "OK",
        "warning_threshold": 0.03,
        "critical_threshold": 0.08,
        "per_category_prev": {"billing": 1.0, "technical": 0.8},
        "per_category_curr": {"billing": 1.0, "technical": 0.9},
        "regressions": [],
        "improvements": ["003"],
    }


@pytest.fixture
def minimal_metadata():
    return {
        "prompt_version": "1.0",
        "prompt_timestamp": "2026-04-17",
        "model": "claude-test",
        "timestamp": "2026-04-17 12:00:00",
        "dataset_size": 10,
        "warning_threshold": 3,
        "critical_threshold": 8,
    }


@pytest.fixture
def sample_curr_data():
    return [
        {
            "id": "001",
            "input": "Test email",
            "expected_output": {"category": "billing", "summary": "Test"},
            "category_match": True,
            "raw_output": '{"category": "billing"}',
        },
        {
            "id": "003",
            "input": "Another email",
            "expected_output": {"category": "technical", "summary": "Tech"},
            "category_match": True,
            "raw_output": '{"category": "technical"}',
        },
    ]


@pytest.fixture
def sample_prev_data():
    return [
        {
            "id": "001",
            "input": "Test email",
            "expected_output": {"category": "billing", "summary": "Test"},
            "category_match": True,
            "raw_output": '{"category": "billing"}',
        },
        {
            "id": "003",
            "input": "Another email",
            "expected_output": {"category": "technical", "summary": "Tech"},
            "category_match": False,
            "raw_output": '{"category": "general"}',
        },
    ]


# --- HTML report generation ---


class TestGenerateHtmlReport:
    def test_returns_valid_html(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        trend = [{"timestamp": "2026-04-16", "pass_rate": 0.90}]
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "<!DOCTYPE html>" in html
        assert "</html>" in html
        assert "Classification Regression Report" in html

    def test_contains_metadata(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "1.0" in html  # prompt version
        assert "claude-test" in html  # model
        assert "2026-04-17" in html  # timestamp

    def test_contains_scorecard(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "90.00%" in html  # prev pass rate
        assert "92.50%" in html  # curr pass rate
        assert "flag-ok" in html  # OK status

    def test_critical_flag_styling(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        minimal_diff_data["flag"] = "CRITICAL"
        minimal_diff_data["delta"] = -0.10
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "flag-critical" in html

    def test_warning_flag_styling(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        minimal_diff_data["flag"] = "WARNING"
        minimal_diff_data["delta"] = -0.05
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "flag-warning" in html

    def test_per_category_table(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "billing" in html
        assert "technical" in html

    def test_improvements_section(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "Improvements" in html
        # ID 003 is an improvement
        assert "003" in html

    def test_no_regressions_message(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "No regressions detected" in html

    def test_regressions_table(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        minimal_diff_data["regressions"] = ["001"]
        minimal_diff_data["improvements"] = []
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "regression-row" in html
        assert "001" in html

    def test_xss_escaping_in_output(self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata):
        """Ensure malicious content is escaped in the report."""
        minimal_diff_data["regressions"] = ["001"]
        sample_curr_data[0]["raw_output"] = '<script>alert("xss")</script>'
        trend = []
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_trend_chart_with_multiple_points(
        self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata
    ):
        trend = [
            {"timestamp": "2026-04-15", "pass_rate": 0.85},
            {"timestamp": "2026-04-16", "pass_rate": 0.90},
            {"timestamp": "2026-04-17", "pass_rate": 0.925},
        ]
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "<svg" in html
        assert "circle" in html

    def test_trend_chart_single_point_message(
        self, minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata
    ):
        trend = [{"timestamp": "2026-04-17", "pass_rate": 0.925}]
        html = generate_html_report(minimal_diff_data, sample_prev_data, sample_curr_data, minimal_metadata, trend)

        assert "Need at least 2 runs" in html

    def test_empty_data(self, minimal_metadata):
        diff_data = {
            "global_pass_rate_prev": 0.0,
            "global_pass_rate_curr": 0.0,
            "delta": 0.0,
            "flag": "OK",
            "per_category_prev": {},
            "per_category_curr": {},
            "regressions": [],
            "improvements": [],
        }
        html = generate_html_report(diff_data, [], [], minimal_metadata, [])

        assert "<!DOCTYPE html>" in html
        assert "</html>" in html
