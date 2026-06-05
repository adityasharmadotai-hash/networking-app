"""
Reply Checker
-------------
Scans Susan's Gmail inbox for replies from contacted leads.
Classifies each reply as:
  - positive    → interested, wants to connect, asks for more info
  - negative    → not interested, unsubscribe, no thanks
  - bounced     → delivery failure, mailer-daemon
  - other       → reply received but unclear intent
"""

import os
import pickle
import re
import base64
import tempfile
from datetime import datetime, timezone
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMAIL_TOKEN_FILE = os.path.join(_BASE_DIR, os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "susan@hiregen.co")


def _get_token_path() -> str:
    """Load Gmail token from env var (Railway), Streamlit secrets, or local file."""
    # 1. Plain env var — Railway
    token_b64 = os.getenv("GMAIL_TOKEN_B64", "")
    if token_b64:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
        tmp.write(base64.b64decode(token_b64))
        tmp.flush()
        tmp.close()
        return tmp.name

    # 2. Streamlit secrets
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is not None:
            import streamlit as st
            token_b64 = st.secrets.get("GMAIL_TOKEN_B64", "")
            if token_b64:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
                tmp.write(base64.b64decode(token_b64))
                tmp.flush()
                tmp.close()
                return tmp.name
    except Exception:
        pass

    # 3. Local file
    return GMAIL_TOKEN_FILE

POSITIVE_KEYWORDS = [
    "interested", "love to", "would love", "let's connect", "lets connect",
    "schedule a call", "set up a call", "tell me more", "send me", "sounds good",
    "great timing", "please share", "open to", "happy to chat", "yes",
    "available", "when are you", "can we", "reach out", "good fit",
]

NEGATIVE_KEYWORDS = [
    "not interested", "no thank you", "no thanks", "not looking",
    "unsubscribe", "remove me", "stop emailing", "do not contact",
    "please don't", "not hiring", "not at this time", "no longer",
    "filled the position", "position has been filled",
]

BOUNCE_KEYWORDS = [
    "delivery status notification", "mail delivery failed",
    "undeliverable", "mailer-daemon", "delivery failure",
    "does not exist", "no such user", "invalid address",
    "account does not exist", "550", "mailbox not found",
]


def get_gmail_service():
    token_path = _get_token_path()
    with open(token_path, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def classify_reply(subject: str, snippet: str, sender: str) -> str:
    text = (subject + " " + snippet + " " + sender).lower()

    # Bounced first — mailer-daemon or delivery failure
    if any(kw in text for kw in BOUNCE_KEYWORDS) or "mailer-daemon" in sender.lower():
        return "bounced"

    # Negative
    if any(kw in text for kw in NEGATIVE_KEYWORDS):
        return "negative"

    # Positive
    if any(kw in text for kw in POSITIVE_KEYWORDS):
        return "positive"

    return "other"


def check_replies_for_lead(service, lead: dict) -> dict | None:
    """
    Search Gmail for any reply from the lead's email address.
    Returns classification dict or None if no reply found.
    """
    contact_email = lead.get("contact_email", "")
    if not contact_email:
        return None

    try:
        # Search for emails FROM the contact TO susan
        query = f"from:{contact_email} to:{SENDER_EMAIL}"
        result = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
        messages = result.get("messages", [])

        if not messages:
            return None

        # Get the most recent reply
        msg = service.users().messages().get(
            userId="me", id=messages[0]["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "")
        sender  = headers.get("From", "")
        snippet = msg.get("snippet", "")

        classification = classify_reply(subject, snippet, sender)

        return {
            "response_status": classification,
            "response_snippet": snippet[:300],
            "response_checked_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        print(f"[Reply Checker] Error checking {contact_email}: {e}")
        return None


def check_all_replies():
    """Check all emailed/following_up leads for replies. Update Supabase."""
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    service  = get_gmail_service()

    # Fetch leads that have been emailed and don't have a positive/negative response yet
    result = supabase.table("leads") \
        .select("id, contact_email, contact_name, company_name, response_status") \
        .in_("status", ["emailed", "following_up"]) \
        .execute()

    leads = result.data
    print(f"[Reply Checker] Checking {len(leads)} leads for replies...")

    updated = 0
    for lead in leads:
        # Skip if already marked positive or negative
        if lead.get("response_status") in ("positive", "negative", "bounced"):
            continue

        reply = check_replies_for_lead(service, lead)
        if reply:
            supabase.table("leads").update(reply).eq("id", lead["id"]).execute()
            print(f"[Reply Checker] {lead['company_name']} ({lead['contact_email']}): {reply['response_status'].upper()}")
            updated += 1
        else:
            # Just update the checked timestamp
            supabase.table("leads").update({
                "response_checked_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", lead["id"]).execute()

    print(f"[Reply Checker] Done. {updated} leads updated.")
    return updated


if __name__ == "__main__":
    check_all_replies()
