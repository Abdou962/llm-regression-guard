"""Tests for src/db.py — SQLite pipeline history storage."""

import sqlite3

from src.db import (
    compare_runs,
    get_case_history,
    get_category_history,
    get_classifications,
    get_connection,
    get_diff,
    get_latest_diffs,
    get_latest_run_id,
    get_latest_runs,
    get_run,
    get_run_results_as_dict,
    get_summary_stats,
    init_db,
    save_diff,
    save_run,
)


# ── Fixtures ──────────────────────────────────────────────

def _make_conn() -> sqlite3.Connection:
    """Create an in-memory SQLite connection with tables."""
    conn = get_connection(":memory:")
    init_db(conn)
    return conn


def _sample_raw_outputs() -> list[dict]:
    return [
        {
            "id": "001",
            "input": "I can't log in",
            "expected_output": {"category": "account", "summary": "Login issue"},
            "category": "account",
            "summary": "Account access issue.",
            "category_match": True,
            "latency": 0.12,
        },
        {
            "id": "002",
            "input": "Why was I charged twice?",
            "expected_output": {"category": "billing", "summary": "Double charge"},
            "category": "billing",
            "summary": "Billing inquiry.",
            "category_match": True,
            "latency": 0.15,
        },
        {
            "id": "003",
            "input": "The app crashes",
            "expected_output": {"category": "technical", "summary": "App crash"},
            "category": "billing",
            "summary": "Billing inquiry.",
            "category_match": False,
            "latency": 0.10,
        },
    ]


def _sample_diff_data(flag: str = "OK", delta: float = 0.0) -> dict:
    return {
        "flag": flag,
        "delta": delta,
        "global_pass_rate_curr": 0.67,
        "global_pass_rate_prev": 0.67,
    }


def test_init_db_creates_tables():
    conn = _make_conn()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {r["name"] for r in tables}
    assert "runs" in table_names
    assert "classifications" in table_names
    assert "diffs" in table_names
    conn.close()


def test_init_db_is_idempotent():
    conn = _make_conn()
    init_db(conn)  
    init_db(conn)  
    conn.close()


def test_save_run_returns_id():
    conn = _make_conn()
    run_id = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    assert run_id == 1
    conn.close()


def test_save_run_stores_correct_counts():
    conn = _make_conn()
    outputs = _sample_raw_outputs()
    run_id = save_run(conn, _sample_diff_data(), outputs, "dummy", "v1")
    run = get_run(conn, run_id)
    assert run["dataset_size"] == 3
    assert run["pass_count"] == 2
    assert run["pass_rate"] == round(2 / 3, 4)
    conn.close()


def test_save_run_stores_classifications():
    conn = _make_conn()
    run_id = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    rows = get_classifications(conn, run_id)
    assert len(rows) == 3
    assert rows[0]["case_id"] == "001"
    assert rows[0]["correct"] == 1
    assert rows[2]["correct"] == 0
    conn.close()


def test_save_run_stores_flag_and_delta():
    conn = _make_conn()
    run_id = save_run(conn, _sample_diff_data("WARNING", -0.05), _sample_raw_outputs(), "claude", "v2")
    run = get_run(conn, run_id)
    assert run["flag"] == "WARNING"
    assert run["delta"] == -0.05
    assert run["model"] == "claude"
    assert run["prompt_version"] == "v2"
    conn.close()


def test_save_run_empty_outputs():
    conn = _make_conn()
    run_id = save_run(conn, _sample_diff_data(), [], "dummy", "v1")
    run = get_run(conn, run_id)
    assert run["dataset_size"] == 0
    assert run["pass_rate"] == 0.0
    assert get_classifications(conn, run_id) == []
    conn.close()


def test_save_multiple_runs():
    conn = _make_conn()
    id1 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    id2 = save_run(conn, _sample_diff_data("OK", 0.05), _sample_raw_outputs(), "claude", "v2")
    assert id2 == id1 + 1
    runs = get_latest_runs(conn, limit=10)
    assert len(runs) == 2
    assert runs[0]["id"] == id2  # newest first
    conn.close()

def test_get_run_not_found():
    conn = _make_conn()
    assert get_run(conn, 999) is None
    conn.close()


def test_get_latest_runs_respects_limit():
    conn = _make_conn()
    for i in range(5):
        save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", f"v{i}")
    runs = get_latest_runs(conn, limit=3)
    assert len(runs) == 3
    assert runs[0]["prompt_version"] == "v4"  # newest
    conn.close()

def test_get_case_history():
    conn = _make_conn()
    save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "claude", "v2")
    history = get_case_history(conn, "001")
    assert len(history) == 2
    assert history[0]["model"] == "claude"  # newest first
    assert history[1]["model"] == "dummy"
    conn.close()


def test_get_case_history_unknown_case():
    conn = _make_conn()
    save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    assert get_case_history(conn, "nonexistent") == []
    conn.close()


def test_get_category_history():
    conn = _make_conn()
    save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    history = get_category_history(conn, "billing")
    assert len(history) == 1
    assert history[0]["total"] == 1
    assert history[0]["correct"] == 1
    assert history[0]["accuracy"] == 1.0
    conn.close()


def test_get_category_history_with_failures():
    conn = _make_conn()
    save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    # technical has 1 case that was predicted wrong
    history = get_category_history(conn, "technical")
    assert len(history) == 1
    assert history[0]["total"] == 1
    assert history[0]["correct"] == 0
    assert history[0]["accuracy"] == 0.0
    conn.close()


# ── compare_runs ──────────────────────────────────────────

def test_compare_identical_runs():
    conn = _make_conn()
    id1 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    id2 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    diffs = compare_runs(conn, id1, id2)
    assert diffs == []  # identical runs
    conn.close()


def test_compare_different_runs():
    conn = _make_conn()
    outputs_v1 = _sample_raw_outputs()
    id1 = save_run(conn, _sample_diff_data(), outputs_v1, "dummy", "v1")

    # v2: case 003 is now correct
    outputs_v2 = _sample_raw_outputs()
    outputs_v2[2]["category"] = "technical"
    outputs_v2[2]["category_match"] = True
    id2 = save_run(conn, _sample_diff_data(), outputs_v2, "claude", "v2")

    diffs = compare_runs(conn, id1, id2)
    assert len(diffs) == 1
    assert diffs[0]["case_id"] == "003"
    assert diffs[0]["correct_a"] == 0
    assert diffs[0]["correct_b"] == 1
    conn.close()


# ── get_summary_stats ─────────────────────────────────────

def test_summary_stats_empty_db():
    conn = _make_conn()
    stats = get_summary_stats(conn)
    assert stats["total_runs"] == 0
    assert stats["total_classifications"] == 0
    conn.close()


def test_summary_stats_with_data():
    conn = _make_conn()
    save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "claude", "v2")
    stats = get_summary_stats(conn)
    assert stats["total_runs"] == 2
    assert stats["total_classifications"] == 6
    assert 0.0 < stats["avg_pass_rate"] <= 1.0
    conn.close()


# ── get_latest_run_id ─────────────────────────────────────

def test_get_latest_run_id_empty():
    conn = _make_conn()
    assert get_latest_run_id(conn) is None
    conn.close()


def test_get_latest_run_id_returns_newest():
    conn = _make_conn()
    save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    id2 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "claude", "v2")
    assert get_latest_run_id(conn) == id2
    conn.close()


# ── get_run_results_as_dict ───────────────────────────────

def test_get_run_results_as_dict_format():
    conn = _make_conn()
    run_id = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    results = get_run_results_as_dict(conn, run_id)
    assert len(results) == 3
    assert "001" in results
    assert results["001"]["category_match"] is True
    assert results["001"]["category"] == "account"
    assert results["001"]["expected_output"]["category"] == "account"
    assert results["003"]["category_match"] is False
    conn.close()


def test_get_run_results_as_dict_empty_run():
    conn = _make_conn()
    run_id = save_run(conn, _sample_diff_data(), [], "dummy", "v1")
    results = get_run_results_as_dict(conn, run_id)
    assert results == {}
    conn.close()


# ── save_diff / get_diff ──────────────────────────────────

def _sample_full_diff_data() -> dict:
    return {
        "global_pass_rate_prev": 0.60,
        "global_pass_rate_curr": 0.67,
        "delta": 0.07,
        "flag": "WARNING",
        "per_category_prev": {"account": 1.0, "billing": 0.5},
        "per_category_curr": {"account": 1.0, "billing": 1.0},
        "regressions": [],
        "improvements": ["002"],
    }


def test_save_diff_returns_id():
    conn = _make_conn()
    id1 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    id2 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "claude", "v2")
    diff_id = save_diff(conn, id2, id1, _sample_full_diff_data())
    assert diff_id == 1
    conn.close()


def test_get_diff_returns_correct_data():
    conn = _make_conn()
    id1 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    id2 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "claude", "v2")
    save_diff(conn, id2, id1, _sample_full_diff_data())
    diff = get_diff(conn, id2)
    assert diff is not None
    assert diff["run_id"] == id2
    assert diff["prev_run_id"] == id1
    assert diff["flag"] == "WARNING"
    assert diff["delta"] == 0.07
    assert diff["per_category_curr"] == {"account": 1.0, "billing": 1.0}
    assert diff["regressions"] == []
    assert diff["improvements"] == ["002"]
    conn.close()


def test_get_diff_not_found():
    conn = _make_conn()
    assert get_diff(conn, 999) is None
    conn.close()


def test_save_diff_no_prev_run():
    conn = _make_conn()
    run_id = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    diff_id = save_diff(conn, run_id, None, _sample_full_diff_data())
    diff = get_diff(conn, run_id)
    assert diff["prev_run_id"] is None
    assert diff_id >= 1
    conn.close()


# ── get_latest_diffs ──────────────────────────────────────

def test_get_latest_diffs():
    conn = _make_conn()
    id1 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", "v1")
    id2 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "claude", "v2")
    id3 = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "claude", "v3")
    save_diff(conn, id2, id1, _sample_full_diff_data())
    save_diff(conn, id3, id2, {**_sample_full_diff_data(), "flag": "OK", "delta": 0.0})
    diffs = get_latest_diffs(conn, limit=5)
    assert len(diffs) == 2
    assert diffs[0]["run_id"] == id3  # newest first
    assert diffs[0]["flag"] == "OK"
    assert diffs[1]["run_id"] == id2
    assert diffs[1]["flag"] == "WARNING"
    conn.close()


def test_get_latest_diffs_respects_limit():
    conn = _make_conn()
    prev_id = None
    for i in range(5):
        run_id = save_run(conn, _sample_diff_data(), _sample_raw_outputs(), "dummy", f"v{i}")
        save_diff(conn, run_id, prev_id, _sample_full_diff_data())
        prev_id = run_id
    diffs = get_latest_diffs(conn, limit=2)
    assert len(diffs) == 2
    conn.close()
