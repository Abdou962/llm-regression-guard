"""
Interactive CLI for human validation of pre-classified emails.

The user reviews each proposal from preclassify_emails() and can:
  [a] Accept   — keep the proposed category and summary as-is
  [m] Modify   — correct the category and/or summary
  [r] Reject   — skip this email entirely
  [q] Quit     — stop reviewing, keep what was validated so far

Validated entries are returned in golden-dataset format, ready for injection.
"""

import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.email_classifier import VALID_CATEGORIES  # noqa: E402

# -- Helpers -----------------------------------------------------------------

DIFFICULTY_CHOICES = ("normal", "short", "sarcastic", "multilingual", "ambiguous")


def _next_id(golden_path: str) -> int:
    """Return the next available numeric ID from the existing golden dataset."""
    if not os.path.exists(golden_path):
        return 1
    with open(golden_path, encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        return 1
    return max(int(entry["id"]) for entry in data) + 1


def _format_id(n: int) -> str:
    """Format a numeric ID as a zero-padded 3-digit string."""
    return f"{n:03d}"


# -- Core function -----------------------------------------------------------


def validate_proposals(
    proposals: list[dict[str, Any]],
    golden_path: str | None = None,
    *,
    input_fn: Any = None,
    print_fn: Any = None,
) -> list[dict[str, Any]]:
    """
    Interactive loop: review each proposal and build golden-dataset entries.

    Parameters
    ----------
    proposals : list of dicts from preclassify_emails()
    golden_path : path to golden dataset (for auto-incrementing IDs)
    input_fn : override for input() — used in tests
    print_fn : override for print() — used in tests

    Returns
    -------
    List of validated entries in golden-dataset format:
        {id, input, expected_output: {category, summary},
         expected_difficulty, notes}
    """
    _input = input_fn or input
    _print = print_fn or print

    # Determine starting ID
    default_path = os.path.join(PROJECT_ROOT, "data", "golden_dataset_v1.json")
    path = golden_path or default_path
    next_id = _next_id(path)

    validated: list[dict[str, Any]] = []
    total = len(proposals)

    _print(f"\n[VALIDATE] {total} proposals to review.")
    _print("  Actions: [a]ccept  [m]odify  [r]eject  [q]uit\n")

    for i, proposal in enumerate(proposals, 1):
        # Display the proposal
        _print(f"\n{'=' * 60}")
        _print(f"  Email {i}/{total}")
        _print(f"{'=' * 60}")
        _print(f"  From:     {proposal.get('sender', '???')}")
        _print(f"  Subject:  {proposal.get('subject', '???')}")
        _print(f"  Date:     {proposal.get('received_at', '???')}")
        body_preview = (proposal.get("body", "") or "")[:200]
        _print(f"  Body:     {body_preview}...")
        _print(f"{'─' * 60}")
        _print(f"  Proposed category: {proposal.get('proposed_category', '???')}")
        _print(f"  Proposed summary:  {proposal.get('proposed_summary', '???')}")
        _print(f"{'─' * 60}")

        # Ask for action
        while True:
            action = _input("  Action [a/m/r/q]: ").strip().lower()
            if action in ("a", "m", "r", "q", ""):
                break
            _print("  [ERROR] Choose: a (accept), m (modify), r (reject), q (quit)")

        if action == "q":
            _print(f"\n[VALIDATE] Quit — {len(validated)} entries validated so far.")
            break

        if action == "r":
            _print("  → Rejected.\n")
            continue

        # Accept or Modify
        if action == "m":
            # Pick category
            cats = list(VALID_CATEGORIES)
            _print(f"\n  Categories: {', '.join(cats)}")
            while True:
                cat_choice = _input(f"  Category [{proposal['proposed_category']}]: ").strip()
                if not cat_choice:
                    category = proposal["proposed_category"]
                    break
                if cat_choice in VALID_CATEGORIES:
                    category = cat_choice
                    break
                _print(f"  [ERROR] Invalid. Choose from: {', '.join(cats)}")

            # Pick summary
            sum_choice = _input(f"  Summary [{proposal['proposed_summary']}]: ").strip()
            summary = sum_choice if sum_choice else proposal["proposed_summary"]
        else:
            # Accept as-is
            category = proposal["proposed_category"]
            summary = proposal["proposed_summary"]

        # Difficulty
        _print(f"\n  Difficulty levels: {', '.join(DIFFICULTY_CHOICES)}")
        while True:
            diff_choice = _input("  Difficulty [normal]: ").strip()
            if not diff_choice:
                difficulty = "normal"
                break
            if diff_choice in DIFFICULTY_CHOICES:
                difficulty = diff_choice
                break
            _print(f"  [ERROR] Invalid. Choose from: {', '.join(DIFFICULTY_CHOICES)}")

        # Notes
        notes = _input("  Notes (optional): ").strip()

        # Build the input text (subject + body, like in preclassify)
        email_input = proposal.get("body", "")
        subject = proposal.get("subject", "")
        if subject:
            email_input = f"{subject} — {email_input}"

        entry = {
            "id": _format_id(next_id),
            "input": email_input,
            "expected_output": {
                "category": category,
                "summary": summary,
            },
            "expected_difficulty": difficulty,
            "notes": notes or f"Imported from {proposal.get('sender', 'unknown')}.",
        }
        validated.append(entry)
        next_id += 1

        _print(f"  → Validated as #{entry['id']} ({category}).\n")

    _print(f"\n[VALIDATE] Done — {len(validated)}/{total} entries validated.")
    return validated


# -- Standalone usage --------------------------------------------------------


if __name__ == "__main__":
    import argparse

    from src.email_fetcher import IMAPConfig, fetch_unread_emails
    from src.preclassify import preclassify_emails

    parser = argparse.ArgumentParser(description="Fetch → Pre-classify → Validate emails")
    parser.add_argument("--limit", type=int, default=10, help="Max emails to fetch")
    parser.add_argument("--golden", default=None, help="Path to golden dataset JSON")
    parser.add_argument("--output", default=None, help="Save validated entries to this file")
    args = parser.parse_args()

    # Step 1 — Fetch
    print("[PIPELINE] Step 1: Fetching emails...")
    config = IMAPConfig.from_env()
    emails = fetch_unread_emails(config, limit=args.limit)
    if not emails:
        print("[PIPELINE] No emails found. Exiting.")
        sys.exit(0)

    # Step 2 — Pre-classify
    print("[PIPELINE] Step 2: Pre-classifying...")
    proposals = preclassify_emails(emails)

    # Step 3 — Validate
    print("[PIPELINE] Step 3: Interactive validation...")
    validated = validate_proposals(proposals, golden_path=args.golden)

    if not validated:
        print("[PIPELINE] No entries validated. Nothing to save.")
        sys.exit(0)

    # Save
    out_path = args.output or os.path.join(PROJECT_ROOT, "data", "validated_entries.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(validated, f, indent=2, ensure_ascii=False)
    print(f"[PIPELINE] Saved {len(validated)} entries to {out_path}")
