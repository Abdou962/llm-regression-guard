"""
Unit tests for report_utils module — JSON/YAML I/O, metadata extraction,
and trend history management.
"""

import json

import yaml

from src.report_utils import (
    extract_model_from_results,
    get_prompt_metadata,
    load_json,
    load_yaml,
    save_json,
    update_trend_history,
)

# --- load_json / save_json ---


def test_load_json(tmp_path):
    data = {"key": "value", "num": 42}
    path = tmp_path / "test.json"
    path.write_text(json.dumps(data))

    result = load_json(str(path))
    assert result == data


def test_save_json(tmp_path):
    data = [1, 2, 3]
    path = tmp_path / "out.json"

    save_json(str(path), data)

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == data


def test_save_json_unicode(tmp_path):
    """Non-ASCII characters should be preserved, not escaped."""
    data = {"emoji": "✅", "text": "résumé"}
    path = tmp_path / "unicode.json"

    save_json(str(path), data)

    raw = path.read_text(encoding="utf-8")
    assert "✅" in raw
    assert "résumé" in raw


# --- load_yaml ---


def test_load_yaml(tmp_path):
    data = {"version": "1.0", "system_prompt": "Classify emails."}
    path = tmp_path / "prompt.yaml"
    path.write_text(yaml.dump(data))

    result = load_yaml(str(path))
    assert result["version"] == "1.0"


# --- get_prompt_metadata ---


def test_get_prompt_metadata(tmp_path):
    data = {"version": "2.0", "timestamp": "2026-04-17"}
    path = tmp_path / "prompt.yaml"
    path.write_text(yaml.dump(data))

    version, timestamp = get_prompt_metadata(str(path))
    assert version == "2.0"
    assert timestamp == "2026-04-17"


def test_get_prompt_metadata_missing_fields(tmp_path):
    data = {"system_prompt": "Classify emails."}
    path = tmp_path / "prompt.yaml"
    path.write_text(yaml.dump(data))

    version, timestamp = get_prompt_metadata(str(path))
    assert version == "unknown"
    assert timestamp == "unknown"


def test_get_prompt_metadata_invalid_file(tmp_path):
    path = tmp_path / "nonexistent.yaml"
    version, timestamp = get_prompt_metadata(str(path))
    assert version == "unknown"
    assert timestamp == "unknown"


def test_get_prompt_metadata_uses_date_fallback(tmp_path):
    """When 'timestamp' is missing, should fall back to 'date'."""
    data = {"version": "1.0", "date": "2025-01-01"}
    path = tmp_path / "prompt.yaml"
    path.write_text(yaml.dump(data))

    _, timestamp = get_prompt_metadata(str(path))
    assert timestamp == "2025-01-01"


# --- extract_model_from_results ---


def test_extract_model_from_token_usage(tmp_path):
    data = [{"token_usage": {"model": "claude-3-opus"}, "raw_output": "{}"}]
    path = tmp_path / "results.json"
    path.write_text(json.dumps(data))

    assert extract_model_from_results(str(path)) == "claude-3-opus"


def test_extract_model_from_model_name(tmp_path):
    data = [{"token_usage": {"model_name": "gpt-4"}, "raw_output": "{}"}]
    path = tmp_path / "results.json"
    path.write_text(json.dumps(data))

    assert extract_model_from_results(str(path)) == "gpt-4"


def test_extract_model_unknown_when_empty(tmp_path):
    data = [{"raw_output": "just text", "token_usage": None}]
    path = tmp_path / "results.json"
    path.write_text(json.dumps(data))

    assert extract_model_from_results(str(path)) == "unknown"


def test_extract_model_from_empty_list(tmp_path):
    path = tmp_path / "results.json"
    path.write_text("[]")

    assert extract_model_from_results(str(path)) == "unknown"


def test_extract_model_handles_missing_file(tmp_path):
    path = tmp_path / "missing.json"
    assert extract_model_from_results(str(path)) == "unknown"


# --- update_trend_history ---


def test_update_trend_creates_new_file(tmp_path):
    path = tmp_path / "trend.json"
    run = {"timestamp": "2026-04-17", "pass_rate": 0.95}

    history = update_trend_history(str(path), run)

    assert len(history) == 1
    assert history[0]["pass_rate"] == 0.95
    assert path.exists()


def test_update_trend_appends(tmp_path):
    path = tmp_path / "trend.json"
    path.write_text(json.dumps([{"timestamp": "2026-04-16", "pass_rate": 0.90}]))

    run = {"timestamp": "2026-04-17", "pass_rate": 0.95}
    history = update_trend_history(str(path), run)

    assert len(history) == 2
    assert history[-1]["pass_rate"] == 0.95


def test_update_trend_caps_at_20(tmp_path):
    path = tmp_path / "trend.json"
    existing = [{"timestamp": f"day-{i}", "pass_rate": 0.90} for i in range(20)]
    path.write_text(json.dumps(existing))

    run = {"timestamp": "day-20", "pass_rate": 0.99}
    history = update_trend_history(str(path), run)

    assert len(history) == 20
    assert history[-1]["pass_rate"] == 0.99
    assert history[0]["timestamp"] == "day-1"  # first entry was dropped


def test_update_trend_handles_corrupt_file(tmp_path):
    path = tmp_path / "trend.json"
    path.write_text("this is not json")

    run = {"timestamp": "2026-04-17", "pass_rate": 0.95}
    history = update_trend_history(str(path), run)

    assert len(history) == 1
