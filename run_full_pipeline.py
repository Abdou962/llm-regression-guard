import subprocess
import sys

# Run the model on the golden dataset
def run_model():
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
