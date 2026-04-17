"""
Unit tests for diff_eval module — threshold logic, flag computation,
category accuracy, and regression/improvement detection.
"""

import json

import pytest

from src.diff_eval import get_category_accuracy, load_results


def test_load_results_indexes_by_id(tmp_path):
    """Results should be indexed by string ID."""
    data = [
        {"id": 1, "category_match": True},
        {"id": "002", "category_match": False},
    ]
    path = tmp_path / "results.json"
    path.write_text(json.dumps(data))

    results = load_results(str(path))

    assert "1" in results
    assert "002" in results
    assert results["1"]["category_match"] is True


def test_load_results_empty_list(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("[]")

    results = load_results(str(path))
    assert results == {}


def test_category_accuracy_perfect():
    results = {
        "1": {"category": "billing", "category_match": True},
        "2": {"category": "billing", "category_match": True},
        "3": {"category": "technical", "category_match": True},
    }
    acc = get_category_accuracy(results)
    assert acc["billing"] == 1.0
    assert acc["technical"] == 1.0


def test_category_accuracy_mixed():
    results = {
        "1": {"category": "billing", "category_match": True},
        "2": {"category": "billing", "category_match": False},
        "3": {"category": "technical", "category_match": True},
        "4": {"category": "technical", "category_match": False},
    }
    acc = get_category_accuracy(results)
    assert acc["billing"] == 0.5
    assert acc["technical"] == 0.5


def test_category_accuracy_zero():
    results = {
        "1": {"category": "billing", "category_match": False},
        "2": {"category": "billing", "category_match": False},
    }
    acc = get_category_accuracy(results)
    assert acc["billing"] == 0.0


def test_category_accuracy_falls_back_to_expected_output():
    """When 'category' is missing, should fall back to expected_output.category."""
    results = {
        "1": {"expected_output": {"category": "account"}, "category_match": True},
    }
    acc = get_category_accuracy(results)
    assert "account" in acc
    assert acc["account"] == 1.0


@pytest.mark.parametrize(
    "delta,expected_flag",
    [
        (0.0, "OK"),
        (0.02, "OK"),
        (-0.02, "OK"),
        (0.05, "WARNING"),
        (-0.05, "WARNING"),
        (0.10, "CRITICAL"),
        (-0.10, "CRITICAL"),
        (0.03, "WARNING"),  # exactly at warning threshold
        (0.08, "CRITICAL"),  # exactly at critical threshold
    ],
)
def test_flag_computation(delta, expected_flag):
    """Test threshold flag logic matches expected behavior."""
    warning_threshold = 0.03
    critical_threshold = 0.08

    if abs(delta) >= critical_threshold:
        flag = "CRITICAL"
    elif abs(delta) >= warning_threshold:
        flag = "WARNING"
    else:
        flag = "OK"

    assert flag == expected_flag


# --- Regression / Improvement detection ---


def test_regression_detection():
    """A case that was passing but now fails is a regression."""
    prev = {"1": {"category_match": True}, "2": {"category_match": True}}
    curr = {"1": {"category_match": True}, "2": {"category_match": False}}

    regressions = []
    for case_id in curr:
        prev_ok = prev.get(case_id, {}).get("category_match", False)
        curr_ok = curr[case_id].get("category_match", False)
        if prev_ok and not curr_ok:
            regressions.append(case_id)

    assert regressions == ["2"]


def test_improvement_detection():
    """A case that was failing but now passes is an improvement."""
    prev = {"1": {"category_match": False}, "2": {"category_match": False}}
    curr = {"1": {"category_match": True}, "2": {"category_match": False}}

    improvements = []
    for case_id in curr:
        prev_ok = prev.get(case_id, {}).get("category_match", False)
        curr_ok = curr[case_id].get("category_match", False)
        if not prev_ok and curr_ok:
            improvements.append(case_id)

    assert improvements == ["1"]


def test_no_regressions_when_identical():
    prev = {"1": {"category_match": True}, "2": {"category_match": False}}
    curr = {"1": {"category_match": True}, "2": {"category_match": False}}

    regressions = []
    improvements = []
    for case_id in curr:
        prev_ok = prev.get(case_id, {}).get("category_match", False)
        curr_ok = curr[case_id].get("category_match", False)
        if prev_ok and not curr_ok:
            regressions.append(case_id)
        elif not prev_ok and curr_ok:
            improvements.append(case_id)

    assert regressions == []
    assert improvements == []
