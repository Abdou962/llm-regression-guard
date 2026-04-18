"""
Inject all preclassified proposals automatically into the golden dataset (no human validation).

Usage:
    python src/inject_auto.py --proposals path/to/proposals.json [--golden data/golden_dataset_v1.json]

Each proposal is converted to golden format and appended with auto-incremented IDs.
"""

import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def next_id(golden):
    if not golden:
        return 1
    return max(int(e["id"]) for e in golden) + 1


def proposal_to_golden(entry, new_id):
    subject = entry.get("subject", "")
    body = entry.get("body", "")
    email_input = f"{subject} — {body}" if subject else body
    return {
        "id": f"{new_id:03d}",
        "input": email_input,
        "expected_output": {
            "category": entry["proposed_category"],
            "summary": entry["proposed_summary"],
        },
        "expected_difficulty": "normal",
        "notes": f"Auto-imported from {entry.get('sender', 'unknown')}",
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Inject proposals automatically into golden dataset")
    parser.add_argument("--proposals", required=True, help="Path to proposals.json (from preclassify_emails)")
    parser.add_argument(
        "--golden",
        default=os.path.join(PROJECT_ROOT, "data", "golden_dataset_v1.json"),
        help="Path to golden dataset JSON",
    )
    args = parser.parse_args()

    golden = load_json(args.golden)
    proposals = load_json(args.proposals)
    if not proposals:
        print("[INJECT-AUTO] No proposals to inject.")
        sys.exit(0)

    start_id = next_id(golden)
    for i, entry in enumerate(proposals):
        golden.append(proposal_to_golden(entry, start_id + i))
    save_json(args.golden, golden)
    print(f"[INJECT-AUTO] Injected {len(proposals)} entries. New total: {len(golden)}")


if __name__ == "__main__":
    main()
