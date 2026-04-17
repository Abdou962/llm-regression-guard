"""
Integration test: runs the full pipeline end-to-end and verifies outputs.
"""

import os
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_run_full_pipeline():
    """Run the full pipeline and verify that the HTML report is generated."""
    script_path = os.path.join(PROJECT_ROOT, "run_full_pipeline.py")

    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=120,
    )

    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    assert result.returncode == 0, f"Pipeline failed with:\n{result.stderr}"

    # Verify outputs exist
    report_path = os.path.join(PROJECT_ROOT, "data", "diff_report.html")
    assert os.path.exists(report_path), "HTML report not generated"

    diff_json_path = os.path.join(PROJECT_ROOT, "data", "diff_report.json")
    assert os.path.exists(diff_json_path), "Diff JSON report not generated"

    raw_outputs_path = os.path.join(PROJECT_ROOT, "data", "raw_outputs.json")
    assert os.path.exists(raw_outputs_path), "Raw outputs not generated"


def test_pipeline_outputs_valid_json():
    """Verify that pipeline JSON outputs are valid."""
    import json

    for filename in ("raw_outputs.json", "diff_report.json", "trend.json"):
        filepath = os.path.join(PROJECT_ROOT, "data", filename)
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            assert data is not None, f"{filename} is empty"
            assert len(data) > 0, f"{filename} has no entries"


def test_raw_outputs_have_required_fields():
    """Verify raw_outputs.json entries have all required fields."""
    import json

    raw_path = os.path.join(PROJECT_ROOT, "data", "raw_outputs.json")
    if not os.path.exists(raw_path):
        pytest.skip("raw_outputs.json not found — run pipeline first")

    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    required_fields = {"id", "input", "expected_output", "category_match", "raw_output"}
    for entry in data:
        missing = required_fields - set(entry.keys())
        assert not missing, f"Entry {entry.get('id')} missing fields: {missing}"
