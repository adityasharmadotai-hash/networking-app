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

# Explicit opt-outs → permanent suppression (never contact again).
UNSUBSCRIBE_KEYWORDS = [
    "unsubscribe", "remove me", "stop emailing", "do not contact",
    "opt out", "opt-out", "take me off", "no thanks", "no thank you",
    "please stop", "don't contact", "do not email",
]

NEGATIVE_KEYWORDS = [
    "not interested", "not looking", "not hiring", "not at this time",
    "no longer", "filled the position", "position has been filled",
    "please don't",
]

BOUNCE_KEYWORDS = [
    "delivery status notification", "mail delivery failed",
    "undeliverable", "mailer-daemon", "delivery failure",
    "does not exist", "no such user", "invalid address",
    "account does not exist", "550", "mailbox not found",
]


def get_gmail_service():
    from agent.email_sender import load_google_credentials
    return build("gmail", "v1", credentials=load_google_credentials())


def classify_reply(subject: str, snippet: str, sender: str) -> str:
    text = (subject + " " + snippet + " " + sender).lower()

    # Bounced first — mailer-daemon or delivery failure
    if any(kw in text for kw in BOUNCE_KEYWORDS) or "mailer-daemon" in sender.lower():
        return "bounced"

    # Explicit opt-out → permanent suppression
    if any(kw in text for kw in UNSUBSCRIBE_KEYWORDS):
        return "unsubscribed"

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
        # Missing read scope affects every lead — let the caller stop early
        # instead of logging the same 403 for all of them.
        if "insufficientPermissions" in str(e) or "insufficient authentication scopes" in str(e):
            raise
        print(f"[Reply Checker] Error checking {contact_email}: {e}")
        return None


# A bounce/NDR arrives FROM mailer-daemon (not from the contact), so the per-lead
# `from:{contact}` search can never catch it. These hints separate a PERMANENT
# (hard) failure — which should mark the lead bounced + suppress the address —
# from a TRANSIENT delay ("will retry"), which Gmail is still retrying.
PERMANENT_BOUNCE_HINTS = [
    "550", "551", "553", "554", "5.1.1", "5.1.10", "5.2.1", "5.4.1", "5.5.0",
    "address not found", "does not exist", "no such user", "user unknown",
    "mailbox not found", "recipient not found", "couldn't be delivered to",
    "wasn't found", "unable to receive mail", "permanent", "permanently",
]
TRANSIENT_BOUNCE_HINTS = [
    "delay", "temporary problem", "will retry", "delivery incomplete",
    "notified if", "being delayed",
]


def check_bounces(service, supabase, lookback_days: int = 3) -> int:
    """Scan mailer-daemon/postmaster NDRs, extract the failed recipient, and mark
    the matching lead as bounced — for PERMANENT failures only (transient delays
    are left alone; Gmail retries those). Hard bounces are also suppressed so we
    never email that address again."""
    try:
        q = f"(from:mailer-daemon OR from:postmaster) newer_than:{lookback_days}d"
        res = service.users().messages().list(userId="me", q=q, maxResults=50).execute()
        bounce_msgs = res.get("messages", [])
    except Exception as e:
        print(f"[Reply Checker] Bounce scan failed: {e}")
        return 0

    if not bounce_msgs:
        return 0

    # Map active-lead emails -> lead row so we can attribute a bounce to a lead.
    leads = supabase.table("leads") \
        .select("id, contact_email, response_status, company_name") \
        .in_("status", ["emailed", "following_up"]).execute().data or []
    by_email = {(l.get("contact_email") or "").strip().lower(): l for l in leads if l.get("contact_email")}
    if not by_email:
        return 0

    updated = 0
    for m in bounce_msgs:
        try:
            msg = service.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["Subject", "X-Failed-Recipients"],
            ).execute()
        except Exception:
            continue

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "")
        failed  = headers.get("X-Failed-Recipients", "")
        snippet = msg.get("snippet", "")
        subj_l  = subject.lower()
        text    = (subject + " " + snippet).lower()

        # Gmail labels failures "(Failure)" and delays "(Delay)". Only a genuine
        # permanent failure should mark the lead bounced.
        is_permanent = ("failure" in subj_l) or any(h in text for h in PERMANENT_BOUNCE_HINTS)
        is_transient = ("delay" in subj_l) or (
            any(h in text for h in TRANSIENT_BOUNCE_HINTS) and "failure" not in subj_l
        )
        if is_transient or not is_permanent:
            continue

        # Which recipient failed? Prefer the explicit header; fall back to any
        # known lead email mentioned in the snippet.
        candidates = [e.strip().lower() for e in failed.split(",") if e.strip()]
        if not candidates:
            candidates = [em for em in by_email if em in snippet.lower()]

        for em in candidates:
            lead = by_email.get(em)
            if not lead or lead.get("response_status") == "bounced":
                continue
            supabase.table("leads").update({
                "response_status": "bounced",
                "response_snippet": (subject or snippet)[:300],
                "response_checked_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", lead["id"]).execute()
            # Hard bounce → never contact this address again.
            try:
                from agent.suppression import record_unsubscribe
                record_unsubscribe(em, reason="bounce")
            except Exception:
                pass
            print(f"[Reply Checker] 🔴 BOUNCED (permanent): {lead.get('company_name')} <{em}>")
            updated += 1

    return updated


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
        # Skip if already resolved (replied, bounced, or opted out)
        if lead.get("response_status") in ("positive", "negative", "bounced", "unsubscribed"):
            continue

        try:
            reply = check_replies_for_lead(service, lead)
        except Exception as e:
            if "insufficientPermissions" in str(e) or "insufficient authentication scopes" in str(e):
                print("[Reply Checker] ⚠️ Gmail token is missing the read scope "
                      "(gmail.readonly). Regenerate GMAIL_TOKEN_B64 with the updated "
                      "scopes to enable reply detection. Skipping reply check.")
                return updated
            raise
        if reply:
            supabase.table("leads").update(reply).eq("id", lead["id"]).execute()
            # Honor opt-outs permanently — add to the suppression list.
            if reply.get("response_status") == "unsubscribed":
                from agent.suppression import record_unsubscribe
                record_unsubscribe(lead.get("contact_email"), reason="reply")
            print(f"[Reply Checker] {lead['company_name']} ({lead['contact_email']}): {reply['response_status'].upper()}")
            updated += 1
        else:
            # Just update the checked timestamp
            supabase.table("leads").update({
                "response_checked_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", lead["id"]).execute()

    # Bounces arrive from mailer-daemon, not from the contact, so they need a
    # separate sweep (the per-lead loop above can never see them).
    try:
        bounced = check_bounces(service, supabase)
        if bounced:
            print(f"[Reply Checker] {bounced} lead(s) marked as bounced.")
        updated += bounced
    except Exception as e:
        print(f"[Reply Checker] Bounce check error: {e}")

    print(f"[Reply Checker] Done. {updated} leads updated.")
    return updated


if __name__ == "__main__":
    check_all_replies()
