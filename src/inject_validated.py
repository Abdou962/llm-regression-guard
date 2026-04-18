"""
Script to inject validated entries into the golden dataset.

Usage:
    python src/inject_validated.py --validated path/to/validated_entries.json [--golden data/golden_dataset_v1.json]

Appends all validated entries to the golden dataset, auto-incrementing IDs.
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


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Inject validated entries into golden dataset")
    parser.add_argument("--validated", required=True, help="Path to validated_entries.json")
    parser.add_argument(
        "--golden",
        default=os.path.join(PROJECT_ROOT, "data", "golden_dataset_v1.json"),
        help="Path to golden dataset JSON",
    )
    args = parser.parse_args()

    golden = load_json(args.golden)
    validated = load_json(args.validated)
    if not validated:
        print("[INJECT] No validated entries to inject.")
        sys.exit(0)

    start_id = next_id(golden)
    for i, entry in enumerate(validated):
        entry = dict(entry)  # copy
        entry["id"] = f"{start_id + i:03d}"
        golden.append(entry)
    save_json(args.golden, golden)
    print(f"[INJECT] Injected {len(validated)} entries. New total: {len(golden)}")


if __name__ == "__main__":
    main()
