
<p align="center">
	<img src="https://img.shields.io/badge/LLM%20Regression%20Detection-Production%20Ready-brightgreen" alt="LLM Regression Detection"/>
	<img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"/>
	<img src="https://img.shields.io/badge/CI-GitHub%20Actions-blue?logo=githubactions&logoColor=white" alt="CI"/>
	<img src="https://img.shields.io/badge/LLM-Claude%20API-blueviolet" alt="Claude API"/>
	<img src="https://img.shields.io/badge/license-MIT-green" alt="License"/>
</p>

# LLM Regression Detection & Reporting Pipeline


## Overview

This repository provides a production-ready pipeline for evaluating LLM-based features (such as a customer support email classifier) against a hand-labeled golden dataset. It tracks regressions, generates HTML reports, sends Slack alerts, and detects slow drift in model performance. All prompt versions and test data are versioned for CI/CD compatibility.


## Features

- **LLM Feature Under Test:** Modular Python function for email classification (category + summary), with prompt as a configurable parameter.
- **Prompt Versioning:** Prompts are stored as YAML files in `/prompts`, each with version, timestamp, system prompt, and few-shot examples.
- **Golden Dataset:** Hand-labeled, versioned JSON in `/data`, with realistic and edge-case emails, expected outputs, difficulty tags, and notes.
- **Evaluation Engine:** Runs all test cases, collects outputs, scores on multiple dimensions (category, summary, latency, tokens), and diffs against previous runs.
- **Reporting & Alerting:** Generates HTML diff reports, sends Slack alerts (pass/warn/fail/slow drift), and tracks 7-run moving averages for drift detection.
- **CI/CD Ready:** Designed for integration with GitHub Actions and containerization (Dockerfile recommended).


## Getting Started

### 1. Clone the repository and install dependencies

```bash
git clone <your-repo-url>
cd llm-regression-pipeline
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Then edit .env with your actual API keys and webhook URL
```


### 3. Directory structure

- `/src`: Core pipeline scripts (model runner, diff, report)
- `/prompts`: Versioned prompt YAMLs
- `/data`: Golden dataset JSON(s)
- `/Scripts`: Slack alerting utilities
- `run_full_pipeline.py`: Orchestrates the full workflow


## Usage

### Run the full pipeline

```bash
python run_full_pipeline.py
```

This will:
- Run the LLM feature on the golden dataset
- Diff results against the previous run
- Generate an HTML report (auto-opens)
- Send Slack alerts if regressions or drift are detected

### Add new test cases
- Edit `/data/golden_dataset_v1.json` and add new entries (with `id`, `input`, `expected output`, `difficulty`, `notes`)

### Add or update prompts
- Place new YAML files in `/prompts` with version, timestamp, and prompt content

### Adjust thresholds
- Edit `.env` or set environment variables for pass/warn/fail/drift thresholds


## CI/CD Integration

- Add a GitHub Action to run `python run_full_pipeline.py` on PRs that modify `/prompts` or `/data`
- Block merges if critical regressions are detected


## Containerization

- Write a `Dockerfile` that installs requirements and runs the pipeline
- Pass API keys and configs as environment variables


## Architecture Decisions

- **Hand-labeled data:** All golden dataset entries are human-verified for maximum evaluation quality
- **Prompt versioning:** Prompts are treated as code and versioned for reproducibility
- **Multi-dimensional scoring:** Goes beyond accuracy to measure summary quality, latency, and token usage
- **Drift detection:** 7-run moving average catches slow degradation missed by per-run checks
- **Slack alerting:** Ensures visibility for regressions and slow drift


## Extending the System

- Add new LLM features as new Python functions and prompt configs
- Expand the golden dataset with new/edge cases as failures are discovered
- Tune thresholds and alerting logic as needed

---
