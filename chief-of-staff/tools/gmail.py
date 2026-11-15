"""Send email / create drafts from one or more Gmail accounts via the Gmail API (OAuth).

Each agent is assigned one account (e.g. ALEX_GMAIL_ACCOUNT in .env).
Connect an account once with:  python scripts/gmail_auth.py
Tokens are saved as gmail_tokens/<email>.json.
"""
import base64
import glob
import json
import os
from email.mime.text import MIMEText
from email.utils import formataddr

from core import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_DIR = os.path.join(ROOT, "gmail_tokens")
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def accounts():
    """Email addresses of connected Gmail accounts."""
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(TOKEN_DIR, "*.json")))


def _resolve(account):
    account = (account or "").strip().lower()
    if not account:
        raise RuntimeError("This agent has no Gmail account assigned (set e.g. ALEX_GMAIL_ACCOUNT in .env).")
    if account not in accounts():
        raise RuntimeError(f"Gmail account {account} is not connected yet. Run `python scripts/gmail_auth.py` "
                           f"and sign in as {account}.")
    return account


def _service(account):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    with open(os.path.join(TOKEN_DIR, f"{account}.json")) as f:
        creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _raw(account, to, subject, body, cc=""):
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    if cc:
        msg["cc"] = cc
    msg["subject"] = subject
    if "@" in account:
        msg["from"] = formataddr((config.SENDER_NAME, account)) if config.SENDER_NAME else account
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_now(from_account, to, subject, body, cc=""):
    acc = _resolve(from_account)
    res = _service(acc).users().messages().send(userId="me", body={"raw": _raw(acc, to, subject, body, cc)}).execute()
    return {"sent": True, "from": acc, "to": to, "gmail_message_id": res.get("id")}


def create_draft(from_account, to, subject, body, cc=""):
    acc = _resolve(from_account)
    res = _service(acc).users().drafts().create(
        userId="me", body={"message": {"raw": _raw(acc, to, subject, body, cc)}}).execute()
    return {"draft_created": True, "from": acc, "to": to, "gmail_draft_id": res.get("id"),
            "note": f"Draft saved in the Drafts folder of {acc}."}
