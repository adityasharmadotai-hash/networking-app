"""Send email / create drafts from your Gmail via the Gmail API (OAuth).

Run `python scripts/gmail_auth.py` once to create gmail_token.json
(or set GMAIL_TOKEN_B64 for cloud deploys).
"""
import base64
import json
import os
from email.mime.text import MIMEText
from email.utils import formataddr

from core import config

ROOT = os.path.dirname(os.path.dirname(__file__))
TOKEN_FILE = os.path.join(ROOT, "gmail_token.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def _creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    raw = config.env("GMAIL_TOKEN_B64")
    if raw:
        info = json.loads(base64.b64decode(raw))
    elif os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            info = json.load(f)
    else:
        raise RuntimeError("Gmail is not connected. Run `python scripts/gmail_auth.py` in chief-of-staff/.")
    creds = Credentials.from_authorized_user_info(info, SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    return creds


def is_connected():
    return bool(config.env("GMAIL_TOKEN_B64")) or os.path.exists(TOKEN_FILE)


def _service():
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_creds(), cache_discovery=False)


def _raw(to, subject, body, cc=""):
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    if cc:
        msg["cc"] = cc
    msg["subject"] = subject
    if config.SENDER_EMAIL:
        msg["from"] = formataddr((config.SENDER_NAME, config.SENDER_EMAIL)) if config.SENDER_NAME else config.SENDER_EMAIL
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_now(to, subject, body, cc=""):
    res = _service().users().messages().send(userId="me", body={"raw": _raw(to, subject, body, cc)}).execute()
    return {"sent": True, "gmail_message_id": res.get("id"), "to": to}


def create_draft(to, subject, body, cc=""):
    res = _service().users().drafts().create(userId="me", body={"message": {"raw": _raw(to, subject, body, cc)}}).execute()
    return {"draft_created": True, "gmail_draft_id": res.get("id"), "to": to,
            "note": "Draft saved in your Gmail Drafts folder."}
