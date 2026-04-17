"""
Shared pytest fixtures for the LLM Regression Pipeline test suite.
"""

import json
import os
import sys

import pytest

from src.email_classifier import PromptConfig

# Ensure project root is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def dummy_prompt_config():
    """Reusable prompt configuration for tests (no API call)."""
    return PromptConfig(
        version="test",
        timestamp="2026-04-14T00:00:00Z",
        system_prompt="Classify the following customer email into a category and provide a summary. Respond with JSON.",
        examples=[
            {"input": "I can't log in to my account.", "category": "account", "summary": "User cannot log in."},
            {"input": "My bill is wrong.", "category": "billing", "summary": "User has a billing issue."},
            {"input": "The app crashes when I click send.", "category": "technical", "summary": "App crashes on send."},
            {
                "input": "What are your business hours?",
                "category": "general",
                "summary": "User asks about business hours.",
            },
        ],
    )


@pytest.fixture
def project_root():
    """Return the absolute path to the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def data_dir():
    """Return the absolute path to the data directory."""
    return os.path.join(PROJECT_ROOT, "data")


@pytest.fixture
def golden_dataset(data_dir):
    """Load and return the golden dataset."""
    path = os.path.join(data_dir, "golden_dataset_v1.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_diff_report():
    """Return a sample diff report for testing."""
    return {
        "global_pass_rate_prev": 0.925,
        "global_pass_rate_curr": 0.925,
        "delta": 0.0,
        "flag": "OK",
        "warning_threshold": 0.03,
        "critical_threshold": 0.08,
        "per_category_prev": {"billing": 1.0, "technical": 0.8, "account": 1.0},
        "per_category_curr": {"billing": 1.0, "technical": 0.8, "account": 1.0},
        "regressions": [],
        "improvements": [],
    }
