"""
Diff evaluation: compare current vs. previous run outputs.
Computes global pass rate, per-category accuracy, and identifies regressions/improvements.
"""

import json
import os
from collections import defaultdict


def load_results(path):
    """Load results and index by string ID."""
    with open(path, encoding="utf-8") as f:
        return {str(r["id"]): r for r in json.load(f)}


def get_category_accuracy(results):
    """Compute per-category accuracy from results."""
    per_cat = defaultdict(lambda: [0, 0])  # [correct, total]
    for r in results.values():
        # Use the predicted category, or fall back to expected_output category
        cat = r.get("category") or r.get("expected_output", {}).get("category", "unknown")
        per_cat[cat][1] += 1
        if r.get("category_match"):
            per_cat[cat][0] += 1
    return {cat: (c / t if t else 0.0) for cat, (c, t) in per_cat.items()}


def main():
    # Configurable thresholds (via env or defaults)
    warning_threshold = float(os.getenv("DIFF_WARNING_THRESHOLD", 0.03))  # 3%
    critical_threshold = float(os.getenv("DIFF_CRITICAL_THRESHOLD", 0.08))  # 8%

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    prev_path = os.path.join(data_dir, "raw_outputs_prev.json")
    curr_path = os.path.join(data_dir, "raw_outputs.json")

    if not os.path.exists(prev_path):
        print("[INFO] No previous outputs found. Skipping diff (first run).")
        # Create a minimal diff report for the report generator
        curr = load_results(curr_path)
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
        return

    prev = load_results(prev_path)
    curr = load_results(curr_path)

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


if __name__ == "__main__":
    main()
