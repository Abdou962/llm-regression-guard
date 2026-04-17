"""
Runs the email classifier on the golden dataset and saves raw outputs.
Uses the real Claude classifier if ANTHROPIC_API_KEY is set, otherwise falls back to a dummy classifier.
"""

import json
import os
import sys
import time
from datetime import datetime

# Ensure project root is in sys.path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


# --- Dummy classifier (fallback when no API key) ---
def _dummy_classify(email_text: str) -> dict:
    """Rule-based fallback classifier for testing without API access."""
    text = (email_text or "").lower()

    if any(
        w in text
        for w in (
            "account",
            "log in",
            "login",
            "locked",
            "password",
            "accnt",
            "2fa",
            "anmelden",
            "sesión",
            "acess",
            "acount",
        )
    ):
        return {"category": "account", "summary": "Account access issue detected."}
    if any(w in text for w in ("invoice", "bill", "charged", "payment", "refund", "prorat")):
        return {"category": "billing", "summary": "Billing-related inquiry detected."}
    if any(w in text for w in ("crash", "bug", "error", "upload", "deleted", "buggy")):
        return {"category": "technical", "summary": "Technical issue detected."}
    if any(w in text for w in ("feature", "dark mode", "export", "csv", "add")):
        return {"category": "feature_request", "summary": "Feature request detected."}
    if any(w in text for w in ("phishing", "security", "someone else", "mixed up")):
        return {"category": "security", "summary": "Security concern detected."}
    return {"category": "general", "summary": "General inquiry."}


def main():
    data_dir = os.path.join(PROJECT_ROOT, "data")
    golden_path = os.path.join(data_dir, "golden_dataset_v1.json")
    raw_outputs_path = os.path.join(data_dir, "raw_outputs.json")
    prev_outputs_path = os.path.join(data_dir, "raw_outputs_prev.json")
    prompt_path = os.path.join(PROJECT_ROOT, "prompts", "v1_billing_classifier.yaml")

    # Backup previous outputs
    if os.path.exists(raw_outputs_path):
        os.replace(raw_outputs_path, prev_outputs_path)

    # Load golden dataset
    with open(golden_path, encoding="utf-8") as f:
        golden_data = json.load(f)

    # Decide classifier mode
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    use_real = api_key and not api_key.startswith("sk-<") and not api_key.startswith("sk-ant-<")

    if use_real:
        from src.email_classifier import classify_email, load_prompt_config

        prompt_config = load_prompt_config(prompt_path)
        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        print(f"[MODE] Real classifier — model: {model}")
    else:
        print("[MODE] Dummy classifier (set ANTHROPIC_API_KEY in .env for real mode)")

    results = []
    total = len(golden_data)

    for i, item in enumerate(golden_data, 1):
        input_text = item.get("input")

        # Handle null / empty inputs
        if not input_text:
            print(f"  [{i}/{total}] Skipping: input is None or empty.")
            expected = item.get("expected_output", {"category": "general", "summary": "No input provided."})
            results.append(
                {
                    "id": item.get("id", i),
                    "input": input_text,
                    "expected_output": expected,
                    "category": "general",
                    "summary": "No input provided.",
                    "category_match": expected.get("category") == "general",
                    "raw_output": json.dumps(
                        {"category": "general", "summary": "No input provided."}, ensure_ascii=False
                    ),
                    "latency": 0.0,
                    "token_usage": {"model": "skip", "timestamp": datetime.now().isoformat()},
                }
            )
            continue

        expected = item.get("expected_output", {"category": "", "summary": ""})

        # Classify
        start_time = time.perf_counter()
        try:
            if use_real:
                result = classify_email(input_text, prompt_config, api_key, model=model)
                model_output = {"category": result.category, "summary": result.summary}
            else:
                model_output = _dummy_classify(input_text)
        except Exception as e:
            print(f"  [{i}/{total}] ERROR: {e}")
            model_output = {"category": "general", "summary": f"Error: {e}"}
        latency = time.perf_counter() - start_time

        category_match = model_output["category"].strip().lower() == expected.get("category", "").strip().lower()

        results.append(
            {
                "id": item.get("id", i),
                "input": input_text,
                "expected_output": expected,
                "category": model_output["category"],
                "summary": model_output["summary"],
                "category_match": category_match,
                "raw_output": json.dumps(model_output, ensure_ascii=False),
                "latency": round(latency, 3),
                "token_usage": {
                    "model": model if use_real else "dummy",
                    "timestamp": datetime.now().isoformat(),
                },
            }
        )

        status = "PASS" if category_match else "FAIL"
        print(
            f"  [{i}/{total}] {status} id={item.get('id', i)}  expected={expected.get('category')}  got={model_output['category']}  ({latency:.2f}s)"
        )

    # Save results
    with open(raw_outputs_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    pass_count = sum(1 for r in results if r["category_match"])
    print(f"\nDone: {pass_count}/{len(results)} passed ({pass_count / len(results):.1%})")
    print(f"Results saved to {raw_outputs_path}")

    # --- Save run + classifications to DB ---
    try:
        from src.db import get_connection, init_db, save_run

        model_name = model if use_real else "dummy"
        conn = get_connection()
        init_db(conn)
        # Minimal diff_data for the run record (full diff computed in step 2)
        run_diff = {
            "flag": "OK",
            "delta": 0.0,
        }
        run_id = save_run(conn, run_diff, results, model_name, "v1_billing_classifier", mode="real" if use_real else "dummy")
        conn.close()
        print(f"[DB] Run #{run_id} saved to pipeline_history.db")
    except Exception as e:
        print(f"[WARN] Could not save to DB: {e}")


if __name__ == "__main__":
    main()
