import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

"""
Quick script to test IMAP connection and fetch a few emails using current .env config.
"""

from src.email_fetcher import IMAPConfig, fetch_unread_emails
from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    config = IMAPConfig.from_env()
    emails = fetch_unread_emails(config, max_emails=3)
    print(f"Fetched {len(emails)} emails.")
    for i, mail in enumerate(emails, 1):
        print(f"\n--- Email #{i} ---")
        print(f"From: {mail.get('sender')}")
        print(f"Subject: {mail.get('subject')}")
        print(f"Date: {mail.get('received_at')}")
        print(f"Body: {mail.get('body')[:200]}...")