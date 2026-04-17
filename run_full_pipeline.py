import os
import subprocess
import sys


def _has_real_api_key() -> bool:
    """Check if a valid Anthropic API key is configured."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(api_key) and not api_key.startswith("sk-<") and not api_key.startswith("sk-ant-<")


# Run the model on the golden dataset
def run_model():
    if _has_real_api_key() and os.getenv("USE_ASYNC_EVAL", "").lower() == "true":
        print("[1/3] Running model on golden dataset (async mode)...")
        result = subprocess.run([sys.executable, "src/async_eval_classifier.py"])
    else:
        print("[1/3] Running model on golden dataset...")
        result = subprocess.run([sys.executable, "src/run_model_on_golden.py"])
    if result.returncode != 0:
        print("[ERROR] Model run failed.")
        sys.exit(result.returncode)


# Run the diff evaluation
def run_diff():
    print("[2/3] Running diff evaluation...")
    result = subprocess.run([sys.executable, "src/diff_eval.py"])
    if result.returncode != 0:
        print("[ERROR] Diff evaluation failed.")
        sys.exit(result.returncode)


# Generate the HTML report and send alerts
def run_report():
    print("[3/3] Generating HTML report and sending alerts...")
    result = subprocess.run([sys.executable, "src/generate_html_report.py"])
    if result.returncode != 0:
        print("[ERROR] Report generation failed.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    run_model()
    run_diff()
    run_report()
    print("\nPipeline completed successfully!")
