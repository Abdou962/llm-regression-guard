"""
Automated enrichment pipeline: fetch → preclassify → inject (no human validation).

Usage:
    python src/enrich_auto.py --max 3

Fetches emails, preclassifies, and injects directly into golden_dataset_v1.json.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
from src.email_fetcher import IMAPConfig, fetch_unread_emails
from src.preclassify import preclassify_emails
from src.inject_auto import proposal_to_golden, next_id, load_json, save_json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLDEN_PATH = os.path.join(PROJECT_ROOT, "data", "golden_dataset_v1.json")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Automated enrichment pipeline")
    parser.add_argument("--max", type=int, default=3, help="Number of emails to fetch")
    args = parser.parse_args()

    config = IMAPConfig.from_env()
    emails = fetch_unread_emails(config, max_emails=args.max)
    if not emails:
        print("[ENRICH-AUTO] No emails fetched.")
        exit(0)
    print(f"[ENRICH-AUTO] {len(emails)} emails fetched.")

    proposals = preclassify_emails(emails)
    print(f"[ENRICH-AUTO] {len(proposals)} emails preclassified.")

    golden = load_json(GOLDEN_PATH)
    start_id = next_id(golden)
    new_entries = [proposal_to_golden(p, start_id + i) for i, p in enumerate(proposals)]
    golden.extend(new_entries)
    save_json(GOLDEN_PATH, golden)
    print(f"[ENRICH-AUTO] Injected {len(new_entries)} new entries into golden_dataset_v1.json.")
