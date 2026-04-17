
<p align="center">
	<img src="https://img.shields.io/badge/LLM%20Regression%20Detection-Production%20Ready-brightgreen" alt="LLM Regression Detection"/>
	<img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"/>
	<img src="https://img.shields.io/badge/CI-GitHub%20Actions-blue?logo=githubactions&logoColor=white" alt="CI"/>
	<img src="https://img.shields.io/badge/LLM-Claude%20API-blueviolet" alt="Claude API"/>
	<img src="https://img.shields.io/badge/tests-129%20passing-success" alt="Tests"/>
	<img src="https://img.shields.io/badge/coverage-%E2%89%A550%25-yellow" alt="Coverage"/>
</p>

# LLM Regression Detection & Reporting Pipeline


## Overview

A production-ready pipeline that evaluates an LLM-based email classifier against a hand-labeled golden dataset, detects regressions, generates HTML reports, stores run history in SQLite, and sends Slack alerts.


## Features

- **3-Mode Classifier:** Real (Claude API), async batch, or dummy (keyword fallback for CI)
- **Prompt Versioning:** YAML-based prompts in `/prompts` with version, timestamp, and few-shot examples
- **Golden Dataset:** 40 hand-labeled test cases in `/data` with difficulty tags and edge cases
- **Diff Engine:** Compares current vs. previous run (from SQLite DB), computes per-category accuracy, flags regressions/improvements
- **SQLite History:** Stores every run, classification, and diff result for fast querying and trend analysis
- **HTML Reports:** Scorecard, per-category tables, SVG trend chart, regression/improvement details
- **Slack Alerts:** Pass/warn/fail alerts + slow drift detection (7-run moving average)
- **CI/CD:** GitHub Actions with lint, tests (Python 3.11 + 3.12), regression checks, and artifact uploads


## Architecture

```
run_full_pipeline.py                # Orchestrator (3 sequential steps)
  ├── src/run_model_on_golden.py    # Step 1: Classify → raw_outputs.json → save to DB
  ├── src/diff_eval.py              # Step 2: Load previous from DB → diff → save diff to DB
  └── src/generate_html_report.py   # Step 3: HTML report + trend + Slack alerts
```

### Data Flow

```
golden_dataset_v1.json
        │
        ▼
  ┌─────────────┐     save run      ┌──────────────────┐
  │  Step 1      │ ───────────────→  │ pipeline_history  │
  │  Classify    │                   │     .db           │
  └──────┬───────┘                   │                   │
         │ raw_outputs.json          │  runs             │
         ▼                           │  classifications  │
  ┌─────────────┐  load previous     │  diffs            │
  │  Step 2      │ ←──────────────── │                   │
  │  Diff        │ ───────────────→  └──────────────────┘
  └──────┬───────┘     save diff
         │ diff_report.json
         ▼
  ┌─────────────┐
  │  Step 3      │ → diff_report.html
  │  Report      │ → trend.json
  │              │ → Slack Alert
  └─────────────┘
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/email_classifier.py` | Core classifier — Claude API with retry + robust JSON parsing |
| `src/async_eval_classifier.py` | Async batch evaluation with LLM-as-judge scoring |
| `src/diff_eval.py` | Pass rates, per-category accuracy, regressions/improvements |
| `src/db.py` | SQLite storage — runs, classifications, diffs tables |
| `src/report_html.py` | HTML report with scorecard, tables, SVG trend chart |
| `src/report_utils.py` | JSON/YAML I/O, metadata extraction, trend history |
| `Scripts/slack_alerter.py` | Slack webhook alerts (pass/warn/fail) |


## Getting Started

### 1. Clone and install

```bash
git clone <your-repo-url>
cd llm-regression-guard
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file (or set environment variables):

```bash
ANTHROPIC_API_KEY=sk-ant-...       # Optional — dummy mode if unset
SLACK_WEBHOOK_URL=https://...      # Optional — no alerts if unset
CLAUDE_MODEL=claude-sonnet-4-20250514  # Optional — default model
```

### 3. Run the pipeline

```bash
python run_full_pipeline.py
```

This will:
1. Run the classifier on all 40 golden dataset cases
2. Save the run + classifications to `pipeline_history.db`
3. Load the previous run from the DB and compute the diff
4. Save the diff results to the DB
5. Generate an HTML report and send Slack alerts if needed

### 4. Run tests

```bash
python -m pytest tests/ -v                          # All 129 tests
python -m pytest tests/ -v --cov=src --cov=Scripts   # With coverage
python -m pytest tests/test_db.py -v                 # DB tests only
```


## Classifier Modes

| Mode | When | How |
|------|------|-----|
| **Dummy** | No `ANTHROPIC_API_KEY` | Keyword-based rules (92.5% accuracy) |
| **Real (sync)** | Valid API key | Claude API, one call per case |
| **Async** | Valid API key + `USE_ASYNC_EVAL=true` | Async batch with LLM-as-judge |


## Threshold Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DIFF_WARNING_THRESHOLD` | `0.03` | Warning if delta ≥ 3% |
| `DIFF_CRITICAL_THRESHOLD` | `0.08` | Critical if delta ≥ 8% |
| `SLOW_DRIFT_THRESHOLD` | `0.90` | Alert if 7-run avg < 90% |


## SQLite Database

The pipeline stores all runs in `data/pipeline_history.db` with 3 tables:

- **`runs`** — One row per pipeline execution (timestamp, model, pass rate, flag, delta)
- **`classifications`** — One row per test case per run (predicted vs expected, correct, latency)
- **`diffs`** — One row per diff (pass rates, per-category accuracy, regressions, improvements)

Query functions in `src/db.py`: `get_latest_runs()`, `get_case_history()`, `get_category_history()`, `compare_runs()`, `get_latest_diffs()`, etc.


## CI/CD

GitHub Actions workflow (`.github/workflows/regression.yml`) runs 5 jobs:

1. **Lint & Format** — `ruff check` + `ruff format --check`
2. **Unit Tests** — Python 3.11 + 3.12 matrix, 129 tests, ≥50% coverage
3. **Regression (Dummy)** — Full pipeline + integration tests + DB verification
4. **Regression (Real)** — Claude API + async eval + Slack alerts (on push to main / schedule / manual)
5. **Docker** — Build verification

Artifacts (reports + DB) are uploaded with 30-day (dummy) / 90-day (real) retention.

