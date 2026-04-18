"""Tests for the interactive validation CLI."""

import json
from unittest.mock import MagicMock

import pytest

from src.validate_cli import (
    DIFFICULTY_CHOICES,
    _format_id,
    _next_id,
    validate_proposals,
)

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture()
def sample_proposals():
    """Proposals as returned by preclassify_emails()."""
    return [
        {
            "message_id": "<1@test>",
            "sender": "alice@example.com",
            "subject": "Can't login",
            "body": "I forgot my password and can't login.",
            "received_at": "2026-04-18T10:00:00",
            "proposed_category": "account",
            "proposed_summary": "Account access issue.",
            "mode": "dummy (keywords)",
            "latency": 0.001,
        },
        {
            "message_id": "<2@test>",
            "sender": "bob@example.com",
            "subject": "Invoice wrong",
            "body": "I was charged $200 instead of $20.",
            "received_at": "2026-04-18T11:00:00",
            "proposed_category": "billing",
            "proposed_summary": "Billing-related inquiry.",
            "mode": "dummy (keywords)",
            "latency": 0.001,
        },
        {
            "message_id": "<3@test>",
            "sender": "carol@example.com",
            "subject": "Hello",
            "body": "Just saying hi!",
            "received_at": "2026-04-18T12:00:00",
            "proposed_category": "general",
            "proposed_summary": "General inquiry.",
            "mode": "dummy (keywords)",
            "latency": 0.001,
        },
    ]


@pytest.fixture()
def golden_file(tmp_path):
    """Create a temporary golden dataset with 3 existing entries."""
    data = [
        {"id": "001", "input": "test1", "expected_output": {}, "expected_difficulty": "normal", "notes": ""},
        {"id": "002", "input": "test2", "expected_output": {}, "expected_difficulty": "normal", "notes": ""},
        {"id": "003", "input": "test3", "expected_output": {}, "expected_difficulty": "normal", "notes": ""},
    ]
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


# -- Unit tests: helpers -----------------------------------------------------


class TestFormatId:
    def test_single_digit(self):
        assert _format_id(1) == "001"

    def test_double_digit(self):
        assert _format_id(42) == "042"

    def test_triple_digit(self):
        assert _format_id(100) == "100"


class TestNextId:
    def test_from_existing_file(self, golden_file):
        assert _next_id(golden_file) == 4

    def test_missing_file(self, tmp_path):
        assert _next_id(str(tmp_path / "nope.json")) == 1

    def test_empty_dataset(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("[]", encoding="utf-8")
        assert _next_id(str(path)) == 1


# -- Accept all --------------------------------------------------------------


class TestAcceptAll:
    def test_accept_all_proposals(self, sample_proposals, golden_file):
        """User hits 'a' + Enter for every prompt."""
        # Inputs: for each email → action=a, difficulty=Enter, notes=Enter
        inputs = iter(["a", "", "", "a", "", "", "a", "", ""])
        mock_input = MagicMock(side_effect=inputs)
        mock_print = MagicMock()

        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=mock_input,
            print_fn=mock_print,
        )

        assert len(result) == 3
        assert result[0]["id"] == "004"
        assert result[1]["id"] == "005"
        assert result[2]["id"] == "006"
        assert result[0]["expected_output"]["category"] == "account"
        assert result[1]["expected_output"]["category"] == "billing"
        assert result[2]["expected_output"]["category"] == "general"
        assert result[0]["expected_difficulty"] == "normal"

    def test_input_contains_subject_and_body(self, sample_proposals, golden_file):
        inputs = iter(["a", "", "", "a", "", "", "a", "", ""])
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert "Can't login" in result[0]["input"]
        assert "password" in result[0]["input"]


# -- Reject all --------------------------------------------------------------


class TestRejectAll:
    def test_reject_all(self, sample_proposals, golden_file):
        inputs = iter(["r", "r", "r"])
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert result == []


# -- Quit early --------------------------------------------------------------


class TestQuitEarly:
    def test_quit_after_first(self, sample_proposals, golden_file):
        """Accept first, then quit."""
        inputs = iter(["a", "", "", "q"])
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert len(result) == 1
        assert result[0]["id"] == "004"

    def test_quit_immediately(self, sample_proposals, golden_file):
        inputs = iter(["q"])
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert result == []


# -- Modify ------------------------------------------------------------------


class TestModify:
    def test_modify_category_and_summary(self, sample_proposals, golden_file):
        """Modify first email: change category to 'security', new summary."""
        inputs = iter(
            [
                "m",  # action
                "security",  # category
                "Security concern.",  # summary
                "normal",  # difficulty
                "Manually corrected",  # notes
                "r",  # reject second
                "r",  # reject third
            ]
        )
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert len(result) == 1
        assert result[0]["expected_output"]["category"] == "security"
        assert result[0]["expected_output"]["summary"] == "Security concern."
        assert result[0]["notes"] == "Manually corrected"

    def test_modify_keep_defaults(self, sample_proposals, golden_file):
        """Modify but press Enter for all fields → keeps proposed values."""
        inputs = iter(
            [
                "m",  # action
                "",  # keep category
                "",  # keep summary
                "",  # keep difficulty (normal)
                "",  # no notes
                "r",  # reject second
                "r",  # reject third
            ]
        )
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert len(result) == 1
        assert result[0]["expected_output"]["category"] == "account"
        assert result[0]["expected_output"]["summary"] == "Account access issue."

    def test_modify_with_custom_difficulty(self, sample_proposals, golden_file):
        inputs = iter(["m", "", "", "sarcastic", "", "r", "r"])
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert result[0]["expected_difficulty"] == "sarcastic"


# -- Edge cases --------------------------------------------------------------


class TestEdgeCases:
    def test_empty_proposals(self, golden_file):
        result = validate_proposals(
            [],
            golden_path=golden_file,
            input_fn=MagicMock(),
            print_fn=MagicMock(),
        )
        assert result == []

    def test_no_golden_file(self, sample_proposals, tmp_path):
        """When golden file doesn't exist, IDs start at 001."""
        inputs = iter(["a", "", "", "r", "r"])
        result = validate_proposals(
            sample_proposals,
            golden_path=str(tmp_path / "nonexistent.json"),
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert result[0]["id"] == "001"

    def test_default_notes_from_sender(self, sample_proposals, golden_file):
        """When notes is empty, default to 'Imported from <sender>'."""
        inputs = iter(["a", "", "", "r", "r"])
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert "alice@example.com" in result[0]["notes"]

    def test_proposal_without_subject(self, golden_file):
        """Email with no subject → input is just the body."""
        proposal = [
            {
                "message_id": "<4@test>",
                "sender": "x@test.com",
                "subject": "",
                "body": "Just the body text.",
                "received_at": "2026-04-18T13:00:00",
                "proposed_category": "general",
                "proposed_summary": "General.",
                "mode": "dummy",
                "latency": 0.0,
            }
        ]
        inputs = iter(["a", "", ""])
        result = validate_proposals(
            proposal,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert result[0]["input"] == "Just the body text."

    def test_invalid_action_then_valid(self, sample_proposals, golden_file):
        """Invalid action is retried, then accept works."""
        inputs = iter(["x", "z", "a", "", "", "r", "r"])
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert len(result) == 1

    def test_mixed_actions(self, sample_proposals, golden_file):
        """Accept, reject, modify → 2 validated entries."""
        inputs = iter(
            [
                "a",
                "",
                "",  # accept first
                "r",  # reject second
                "m",
                "technical",
                "Bug.",
                "",
                "",  # modify third
            ]
        )
        result = validate_proposals(
            sample_proposals,
            golden_path=golden_file,
            input_fn=MagicMock(side_effect=inputs),
            print_fn=MagicMock(),
        )
        assert len(result) == 2
        assert result[0]["expected_output"]["category"] == "account"
        assert result[1]["expected_output"]["category"] == "technical"
        assert result[0]["id"] == "004"
        assert result[1]["id"] == "005"


# -- Difficulty choices constant ---------------------------------------------


class TestConstants:
    def test_difficulty_choices_contains_normal(self):
        assert "normal" in DIFFICULTY_CHOICES

    def test_difficulty_choices_count(self):
        assert len(DIFFICULTY_CHOICES) >= 3
