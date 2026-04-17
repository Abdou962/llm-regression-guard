"""
Diff evaluation: compare current vs. previous run outputs.
Computes global pass rate, per-category accuracy, and identifies regressions/improvements.
Uses the DB for previous results when available, falls back to raw_outputs_prev.json.
"""

import json
import os
import sys
from collections import defaultdict
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def load_results(path: str) -> dict[str, dict[str, Any]]:
    """Load results and index by string ID."""
    with open(path, encoding="utf-8") as f:
        return {str(r["id"]): r for r in json.load(f)}


def get_category_accuracy(results: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Compute per-category accuracy from results."""
    per_cat = defaultdict(lambda: [0, 0])  # [correct, total]
    for r in results.values():
        # Use the predicted category, or fall back to expected_output category
        cat = r.get("category") or r.get("expected_output", {}).get("category", "unknown")
        per_cat[cat][1] += 1
        if r.get("category_match"):
            per_cat[cat][0] += 1
    return {cat: (c / t if t else 0.0) for cat, (c, t) in per_cat.items()}


def _load_previous_from_db() -> tuple[dict[str, dict[str, Any]] | None, int | None]:
    """Try to load previous results from DB. Returns (results_dict, run_id) or (None, None).

    The latest run is the current one (saved in Step 1), so we need the second-to-last.
    """
    try:
        from src.db import get_connection, get_latest_runs, get_run_results_as_dict, init_db

        conn = get_connection()
        init_db(conn)
        runs = get_latest_runs(conn, limit=2)
        if len(runs) < 2:
            conn.close()
            return None, None
        prev_run = runs[1]  # second most recent = previous run
        prev_id = prev_run["id"]
        results = get_run_results_as_dict(conn, prev_id)
        conn.close()
        if not results:
            return None, None
        print(f"[DB] Loaded previous results from run #{prev_id} ({len(results)} cases)")
        return results, prev_id
    except Exception as e:
        print(f"[WARN] Could not load from DB: {e}")
        return None, None


def _save_diff_to_db(diff_report: dict[str, Any], current_run_id: int | None, prev_run_id: int | None) -> None:
    """Save diff results to DB."""
    try:
        from src.db import get_connection, get_latest_run_id, init_db, save_diff

        conn = get_connection()
        init_db(conn)
        run_id = current_run_id or get_latest_run_id(conn)
        if run_id is None:
            conn.close()
            return
        diff_id = save_diff(conn, run_id, prev_run_id, diff_report)
        conn.close()
        print(f"[DB] Diff #{diff_id} saved (run #{run_id} vs #{prev_run_id or 'none'})")
    except Exception as e:
        print(f"[WARN] Could not save diff to DB: {e}")


def main() -> None:
    # Configurable thresholds (via env or defaults)
    warning_threshold = float(os.getenv("DIFF_WARNING_THRESHOLD", 0.03))  # 3%
    critical_threshold = float(os.getenv("DIFF_CRITICAL_THRESHOLD", 0.08))  # 8%

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    prev_path = os.path.join(data_dir, "raw_outputs_prev.json")
    curr_path = os.path.join(data_dir, "raw_outputs.json")

    curr = load_results(curr_path)

    # --- Try DB first for previous results, fall back to file ---
    prev, prev_run_id = _load_previous_from_db()

    if prev is None:
        if os.path.exists(prev_path):
            prev = load_results(prev_path)
            print(f"[FILE] Loaded previous results from {prev_path}")
        else:
            print("[INFO] No previous outputs found. Skipping diff (first run).")
            curr_pass = sum(1 for r in curr.values() if r.get("category_match")) / len(curr) if curr else 0
            diff_report = {
                "global_pass_rate_prev": curr_pass,
                "global_pass_rate_curr": curr_pass,
                "delta": 0.0,
                "flag": "OK",
                "warning_threshold": warning_threshold,
                "critical_threshold": critical_threshold,
                "per_category_prev": get_category_accuracy(curr),
                "per_category_curr": get_category_accuracy(curr),
                "regressions": [],
                "improvements": [],
            }
            output_path = os.path.join(data_dir, "diff_report.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(diff_report, f, indent=2, ensure_ascii=False)
            print(f"First-run diff report saved to {output_path}")
            _save_diff_to_db(diff_report, None, None)
            return

    # Global pass rate
    prev_pass = sum(1 for r in prev.values() if r.get("category_match")) / len(prev) if prev else 0
    curr_pass = sum(1 for r in curr.values() if r.get("category_match")) / len(curr) if curr else 0
    delta = curr_pass - prev_pass

    # Significance flag
    if abs(delta) >= critical_threshold:
        flag = "CRITICAL"
    elif abs(delta) >= warning_threshold:
        flag = "WARNING"
    else:
        flag = "OK"

    print(f"Global pass rate: {prev_pass:.2%} -> {curr_pass:.2%} (delta {delta:+.2%})  [{flag}]")
    print(f"  Thresholds: warning={warning_threshold * 100:.1f}%, critical={critical_threshold * 100:.1f}%")

    # Per-category accuracy
    prev_cat = get_category_accuracy(prev)
    curr_cat = get_category_accuracy(curr)
    cats = sorted(set(prev_cat) | set(curr_cat))

    print("\nPer-category accuracy:")
    for cat in cats:
        p = prev_cat.get(cat, 0.0)
        c = curr_cat.get(cat, 0.0)
        cat_delta = c - p
        if abs(cat_delta) >= critical_threshold:
            cat_flag = "CRITICAL"
        elif abs(cat_delta) >= warning_threshold:
            cat_flag = "WARNING"
        else:
            cat_flag = "OK"
        print(f"  {cat}: {p:.2%} -> {c:.2%} (delta {cat_delta:+.2%})  [{cat_flag}]")

    # Regressions and improvements
    regressions = []
    improvements = []
    for case_id in curr:
        prev_ok = prev.get(case_id, {}).get("category_match", False)
        curr_ok = curr[case_id].get("category_match", False)
        if prev_ok and not curr_ok:
            regressions.append(case_id)
        elif not prev_ok and curr_ok:
            improvements.append(case_id)

    print(f"\nRegressions (pass->fail): {regressions}")
    print(f"Improvements (fail->pass): {improvements}")

    # Save diff report
    diff_report = {
        "global_pass_rate_prev": prev_pass,
        "global_pass_rate_curr": curr_pass,
        "delta": delta,
        "flag": flag,
        "warning_threshold": warning_threshold,
        "critical_threshold": critical_threshold,
        "per_category_prev": prev_cat,
        "per_category_curr": curr_cat,
        "regressions": regressions,
        "improvements": improvements,
    }
    output_path = os.path.join(data_dir, "diff_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(diff_report, f, indent=2, ensure_ascii=False)
    print(f"\nDiff report saved to {output_path}")

    # --- Save diff to DB ---
    _save_diff_to_db(diff_report, None, prev_run_id)


if __name__ == "__main__":
    main()
