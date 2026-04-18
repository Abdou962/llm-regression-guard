"""
Pre-classify fetched emails before injecting them into the golden dataset.

Takes raw emails from email_fetcher, runs them through the classifier
(real Claude or keyword-based dummy), and returns proposals ready for
human review.
"""

import os
import time
from typing import Any

from src.email_classifier import VALID_CATEGORIES


# -- Dummy classifier (same logic as run_model_on_golden) --------------------


def _dummy_classify(text: str) -> dict[str, str]:
    """Keyword-based fallback when no API key is available."""
    t = (text or "").lower()

    if any(w in t for w in ("account", "log in", "login", "locked", "password", "2fa")):
        return {"category": "account", "summary": "Account access issue."}
    if any(w in t for w in ("invoice", "bill", "charged", "payment", "refund")):
        return {"category": "billing", "summary": "Billing-related inquiry."}
    if any(w in t for w in ("crash", "bug", "error", "upload", "deleted")):
        return {"category": "technical", "summary": "Technical issue."}
    if any(w in t for w in ("feature", "dark mode", "export", "csv", "add")):
        return {"category": "feature_request", "summary": "Feature request."}
    if any(w in t for w in ("phishing", "security", "someone else")):
        return {"category": "security", "summary": "Security concern."}
    return {"category": "general", "summary": "General inquiry."}


# -- Detect which mode we're running in -------------------------------------


def _is_real_mode() -> bool:
    """Check if we have a usable Anthropic API key."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(key and not key.startswith("sk-<") and not key.startswith("sk-ant-<"))


# -- Main function -----------------------------------------------------------


def preclassify_emails(
    emails: list[dict[str, Any]],
    prompt_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Run each email through the classifier and return proposals.

    Each proposal is the original email dict + these keys:
        proposed_category, proposed_summary, mode, latency

    If ANTHROPIC_API_KEY is set and valid → uses real Claude.
    Otherwise → falls back to the dummy keyword classifier.
    """
    use_real = _is_real_mode()

    # Only import Claude stuff if we actually need it
    if use_real:
        from src.email_classifier import classify_email, load_prompt_config

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = prompt_path or os.path.join(project_root, "prompts", "v1_billing_classifier.yaml")
        prompt_config = load_prompt_config(path)
        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        mode = f"real ({model})"
    else:
        mode = "dummy (keywords)"

    print(f"[PRE-CLASSIFY] Mode: {mode}")
    print(f"[PRE-CLASSIFY] {len(emails)} emails to classify\n")

    proposals: list[dict[str, Any]] = []

    for i, mail in enumerate(emails, 1):
        # Build the text we'll classify — subject + body, like a real support email
        text = f"{mail.get('subject', '')} — {mail.get('body', '')}"

        start = time.perf_counter()
        try:
            if use_real:
                result = classify_email(text, prompt_config, api_key, model=model)
                category = result.category
                summary = result.summary
            else:
                out = _dummy_classify(text)
                category = out["category"]
                summary = out["summary"]
        except Exception as exc:
            print(f"  [{i}/{len(emails)}] ERROR: {exc}")
            category = "general"
            summary = f"Classification failed: {exc}"
        elapsed = time.perf_counter() - start

        # Sanity check
        if category not in VALID_CATEGORIES:
            category = "general"

        proposal = {
            **mail,
            "proposed_category": category,
            "proposed_summary": summary,
            "mode": mode,
            "latency": round(elapsed, 3),
        }
        proposals.append(proposal)

        # Quick progress indicator
        subj = mail.get("subject", "???")[:50]
        print(f"  [{i}/{len(emails)}] {category:<16} | {subj}")

    print(f"\n[PRE-CLASSIFY] Done — {len(proposals)} proposals ready for review.")
    return proposals
