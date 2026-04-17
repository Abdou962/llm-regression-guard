"""
Generates the HTML diff report, updates trend history, and sends Slack alerts.
"""
import os
import sys
from datetime import datetime

# Ensure src/ and project root are in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
for p in (PROJECT_ROOT, SRC_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from report_utils import (
    load_json,
    get_prompt_metadata,
    extract_model_from_results,
    update_trend_history,
)
from report_html import generate_html_report


def main():
    """Main function to generate the diff report."""
    data_dir = os.path.join(PROJECT_ROOT, "data")
    diff_path = os.path.join(data_dir, "diff_report.json")
    prev_path = os.path.join(data_dir, "raw_outputs_prev.json")
    curr_path = os.path.join(data_dir, "raw_outputs.json")
    prompt_path = os.path.join(PROJECT_ROOT, "prompts", "v1_billing_classifier.yaml")
    trend_path = os.path.join(data_dir, "trend.json")

    print("Loading data...")
    diff_data = load_json(diff_path)
    prev_data = load_json(prev_path) if os.path.exists(prev_path) else []
    curr_data = load_json(curr_path)

    print("Extracting metadata...")
    prompt_version, prompt_timestamp = get_prompt_metadata(prompt_path)
    model = extract_model_from_results(curr_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metadata = {
        "prompt_version": prompt_version,
        "prompt_timestamp": prompt_timestamp,
        "model": model,
        "timestamp": now,
        "dataset_size": len(curr_data),
        "warning_threshold": diff_data.get("warning_threshold", 3),
        "critical_threshold": diff_data.get("critical_threshold", 8),
    }

    print("Updating trend history...")
    trend_data = update_trend_history(trend_path, {
        "timestamp": now,
        "pass_rate": diff_data["global_pass_rate_curr"],
        "prompt_version": prompt_version,
        "model": model,
    })

    # --- Slow drift detection ---
    SLOW_DRIFT_WINDOW = 7
    SLOW_DRIFT_THRESHOLD = float(os.getenv("SLOW_DRIFT_THRESHOLD", 0.90))
    slow_drift_alerted = False

    if len(trend_data) >= SLOW_DRIFT_WINDOW:
        last_runs = trend_data[-SLOW_DRIFT_WINDOW:]
        avg = sum(t["pass_rate"] for t in last_runs) / SLOW_DRIFT_WINDOW
        # Only alert if no single run triggered a WARNING/CRITICAL, but avg is below threshold
        recent_flags = [
            (t.get("flag") or diff_data.get("flag") if t["timestamp"] == now else None)
            for t in last_runs
        ]
        if avg < SLOW_DRIFT_THRESHOLD and all(f in (None, "OK") for f in recent_flags):
            try:
                from Scripts.slack_alerter import send_simple_alert
                msg = f"⏳ Slow drift detected: 7-run avg pass rate = {avg:.2%} (< {SLOW_DRIFT_THRESHOLD:.0%})"
                send_simple_alert(msg, status="warn")
                print("[ALERT] Slow drift warning sent to Slack.")
                slow_drift_alerted = True
            except Exception as e:
                print(f"[WARN] Could not send slow drift alert: {e}")

    # --- Slack alert for regression or critical/warning ---
    try:
        from Scripts.slack_alerter import send_simple_alert
        if diff_data.get("flag") in ("CRITICAL", "WARNING"):
            msg = (
                f"{diff_data['flag']} — Regression detected! "
                f"Pass rate: {diff_data['global_pass_rate_prev']:.2%} → {diff_data['global_pass_rate_curr']:.2%} "
                f"(Delta {diff_data['delta']:+.2%}) | Regressions: {len(diff_data.get('regressions', []))}"
            )
            status = "fail" if diff_data["flag"] == "CRITICAL" else "warn"
            send_simple_alert(msg, status=status)
            print(f"[ALERT] {diff_data['flag']} alert sent to Slack.")
    except Exception as e:
        print(f"[WARN] Could not send regression alert: {e}")

    print("Generating HTML report...")
    html_report = generate_html_report(diff_data, prev_data, curr_data, metadata, trend_data)
    output_path = os.path.join(data_dir, "diff_report.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_report)

    print(f"\n{'='*60}")
    print(f"Report saved to: {output_path}")
    print(f"Summary: {diff_data['global_pass_rate_prev']:.2%} -> {diff_data['global_pass_rate_curr']:.2%} (Delta: {diff_data['delta']:+.2%})")
    print(f"Status: {diff_data['flag']}")
    print(f"Regressions: {len(diff_data.get('regressions', []))} | Improvements: {len(diff_data.get('improvements', []))}")
    if slow_drift_alerted:
        print(f"[SLOW DRIFT] 7-run moving average below threshold: {SLOW_DRIFT_THRESHOLD:.0%}")
    print(f"{'='*60}")

    # Auto-open report in browser
    try:
        import webbrowser
        webbrowser.open(os.path.abspath(output_path))
    except Exception as e:
        print(f"[INFO] Could not auto-open report: {e}")


if __name__ == "__main__":
    main()