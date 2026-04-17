# CLAUDE.md — Project Intelligence for Claude Code

> This file provides context and skills for Claude when working on this project.
> It is automatically read by Claude Code at the start of each session.

---

## Project Overview

**LLM Regression Detection & Reporting Pipeline** — A production-ready system that evaluates
an LLM-based email classifier against a hand-labeled golden dataset, detects regressions,
generates HTML reports, and sends Slack alerts.

## Architecture

```
run_full_pipeline.py          # Orchestrator (3 sequential steps)
  ├── src/run_model_on_golden.py   # Step 1: Run classifier on golden dataset
  ├── src/diff_eval.py             # Step 2: Compare current vs previous results
  └── src/generate_html_report.py  # Step 3: Generate HTML report + Slack alerts
```

### Key Components

| Module | Purpose |
|--------|---------|
| `src/email_classifier.py` | Core classifier — calls Claude API with retry + robust JSON parsing |
| `src/async_eval_classifier.py` | Async batch evaluation with LLM-as-judge scoring |
| `src/diff_eval.py` | Computes pass rates, per-category accuracy, regressions/improvements |
| `src/report_html.py` | Generates HTML report with scorecard, tables, SVG trend chart |
| `src/report_utils.py` | JSON/YAML I/O, metadata extraction, trend history management |
| `Scripts/slack_alerter.py` | Sends Slack alerts via webhook (pass/warn/fail) |
| `Scripts/slack_utils.py` | Status colors and emojis for Slack |

## Tech Stack

- **Language**: Python 3.11+
- **LLM**: Anthropic Claude (claude-sonnet-4-20250514 default)
- **Validation**: Pydantic models for type safety
- **Config**: YAML prompts, JSON datasets, `.env` for secrets
- **CI/CD**: GitHub Actions
- **Container**: Docker (Python 3.11-slim)

## Code Conventions

### Style
- Use double quotes for strings
- Type hints on all public functions
- Docstrings on all modules and public functions
- f-strings for formatting
- `snake_case` for functions/variables, `PascalCase` for classes

### Imports
- Standard library first, then third-party, then local
- Module-level imports (not inside functions) — required for mocking in tests
- Use `PROJECT_ROOT` pattern for reliable path resolution:
  ```python
  PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
  if PROJECT_ROOT not in sys.path:
      sys.path.insert(0, PROJECT_ROOT)
  ```

### Error Handling
- Never silently swallow exceptions (`except: pass` is forbidden)
- Use specific exception types
- Log errors with `[ERROR]`, warnings with `[WARN]`, info with `[INFO]`

### Testing
- All tests in `tests/` directory
- **Mock the API** — never call real Claude in tests
- Use `unittest.mock.patch` on module-level imports
- Fixtures in `@pytest.fixture` functions
- Parametrize with `@pytest.mark.parametrize` for multiple cases

## Data Flow

```
golden_dataset_v1.json  →  run_model_on_golden.py  →  raw_outputs.json
                                                        (backup → raw_outputs_prev.json)

raw_outputs.json + raw_outputs_prev.json  →  diff_eval.py  →  diff_report.json

diff_report.json + raw_outputs*.json  →  generate_html_report.py  →  diff_report.html
                                                                      trend.json
                                                                      Slack alerts
```

## Important Patterns

### Dual-Mode Classifier
`run_model_on_golden.py` has two modes:
- **Real mode**: Uses Claude API when `ANTHROPIC_API_KEY` is set and valid
- **Dummy mode**: Uses keyword-based fallback when no API key (for CI/testing)

Detection logic:
```python
use_real = api_key and not api_key.startswith("sk-<") and not api_key.startswith("sk-ant-<")
```

### Robust JSON Parsing
`email_classifier._parse_classification()` has 4-level fallback:
1. Direct JSON parse
2. JSON inside markdown code fences
3. Brace-delimited JSON extraction
4. Regex key-value extraction

### Threshold System
Configurable via environment variables:
- `DIFF_WARNING_THRESHOLD` (default 3%)
- `DIFF_CRITICAL_THRESHOLD` (default 8%)
- `SLOW_DRIFT_THRESHOLD` (default 90%)

### Categories
6 valid categories: `billing`, `technical`, `account`, `general`, `feature_request`, `security`
Defined in `src/email_classifier.py` as `VALID_CATEGORIES` tuple.

## Common Tasks

### Add a new test case
1. Add entry to `data/golden_dataset_v1.json` with: `id`, `input`, `expected_output`, `expected_difficulty`, `notes`
2. Run `python run_full_pipeline.py` to verify

### Add a new category
1. Add to `VALID_CATEGORIES` in `src/email_classifier.py`
2. Add to `Literal` type in `EmailClassification`
3. Add to system prompt in `prompts/v1_billing_classifier.yaml` (with example)
4. Add keyword rules in `run_model_on_golden.py::_dummy_classify()`
5. Update tests

### Update the prompt
1. Create new YAML in `prompts/` (e.g., `v2_billing_classifier.yaml`)
2. Update the path reference in `run_model_on_golden.py` and `generate_html_report.py`
3. Run pipeline to evaluate impact

### Run tests
```bash
python -m pytest tests/ -v                    # All tests
python -m pytest tests/test_email_classifier.py -v  # Unit tests only
```

## Known Limitations

- Dummy classifier fails on 3/40 cases (IDs: 017, 037, 040) due to keyword overlap
- `report_html.py` uses inline CSS (no external framework)
- Slack webhook has no signature verification
- No rate limiting on Claude API calls in sync mode

## File Dependencies

```
email_classifier.py  ← used by run_model_on_golden.py, async_eval_classifier.py
report_utils.py      ← used by generate_html_report.py
report_html.py       ← used by generate_html_report.py
slack_utils.py       ← used by slack_alerter.py
slack_alerter.py     ← used by generate_html_report.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | No* | — | Claude API key (*dummy mode if unset) |
| `SLACK_WEBHOOK_URL` | No | — | Slack webhook for alerts |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Claude model to use |
| `DIFF_WARNING_THRESHOLD` | No | `0.03` | Warning threshold (3%) |
| `DIFF_CRITICAL_THRESHOLD` | No | `0.08` | Critical threshold (8%) |
| `SLOW_DRIFT_THRESHOLD` | No | `0.90` | Slow drift threshold (90%) |
