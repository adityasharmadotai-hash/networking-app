import os
import json
import base64
import hashlib
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv
import pickle

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "susan@hiregen.co")
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMAIL_TOKEN_FILE = os.path.join(_BASE_DIR, os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json"))
GMAIL_CREDENTIALS_FILE = os.path.join(_BASE_DIR, os.getenv("GMAIL_CREDENTIALS_FILE", "gmail_credentials.json"))
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",   # needed to detect replies
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _read_token_bytes() -> bytes | None:
    """Raw token bytes from GMAIL_TOKEN_B64 (env or Streamlit secrets) or the local file."""
    # 1. Plain env var — works on Render/Railway and any cloud server
    token_b64 = os.getenv("GMAIL_TOKEN_B64", "")

    # 2. Streamlit secrets — only if a secrets.toml exists (avoids the error banner)
    if not token_b64:
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            if get_script_run_ctx() is not None:
                secrets_paths = [
                    os.path.expanduser("~/.streamlit/secrets.toml"),
                    os.path.join(_BASE_DIR, ".streamlit", "secrets.toml"),
                ]
                if any(os.path.exists(p) for p in secrets_paths):
                    import streamlit as st
                    token_b64 = st.secrets.get("GMAIL_TOKEN_B64", "")
        except Exception:
            pass

    if token_b64:
        return base64.b64decode(token_b64)

    # 3. Fall back to local file (development)
    if os.path.exists(GMAIL_TOKEN_FILE):
        with open(GMAIL_TOKEN_FILE, "rb") as f:
            return f.read()
    return None


def _creds_from_bytes(data: bytes):
    """Build Credentials from token bytes. Prefers JSON (portable across
    google-auth versions); falls back to a legacy pickle for older tokens."""
    try:
        info = json.loads(data.decode("utf-8"))
        return Credentials.from_authorized_user_info(info, SCOPES)
    except Exception:
        return pickle.loads(data)


def load_google_credentials():
    """Return valid Google OAuth credentials (refreshing if expired). Shared by
    Gmail sending, reply checking, and Google Sheets access."""
    data = _read_token_bytes()
    creds = _creds_from_bytes(data) if data else None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Persist locally as portable JSON (dev convenience; ignored on read-only hosts).
        try:
            with open(GMAIL_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        except Exception:
            pass
    return creds

EMAIL_TEMPLATES = {
    "intro": {
        "subject": "{company} — a candidate for your {short_role} opening",
        "body": """Hi {first_name},

I saw that {company} is hiring for a {role} — exciting to see the team growing.

I lead candidate placement at HireGen, and I have someone I genuinely think is worth a look for this role: they're actively interviewing, have directly relevant experience, and could ramp quickly.

Rather than send a résumé out of the blue, would you be open to a quick 15-minute call this week? And if the timing isn't right, no worries at all.

Thanks,
Susan
Susan · HireGen
susan@hiregen.co

P.S. If you'd prefer I don't follow up, just reply "no thanks" and I'll close this out.""",
    },
    "followup_1": {
        "subject": "Re: {company} — a candidate for your {short_role} opening",
        "body": """Hi {first_name},

Following up on my note about the {role} role at {company} — the candidate I mentioned is still available and keen.

Would you have 15 minutes this week? Happy to work around your calendar.

Thanks,
Susan
Susan · HireGen
susan@hiregen.co""",
    },
    "followup_2": {
        "subject": "Re: {company} — a candidate for your {short_role} opening",
        "body": """Hi {first_name},

I know things move fast — just flagging that our candidate for your {short_role} role is still interested in {company}.

Glad to send a short profile so you can evaluate without a call. Want me to?

Best,
Susan
Susan · HireGen
susan@hiregen.co""",
    },
    "followup_3": {
        "subject": "Re: {company} — a candidate for your {short_role} opening",
        "body": """Hi {first_name},

Still think this could be a strong fit on both sides — our candidate has hands-on experience with exactly what {company} needs for the {short_role} role.

Want me to send a profile, or grab 15 minutes?

Thanks,
Susan
Susan · HireGen
susan@hiregen.co""",
    },
    "followup_4": {
        "subject": "Re: {company} — a candidate for your {short_role} opening",
        "body": """Hi {first_name},

A couple more nudges from me at most — I don't want to crowd your inbox.

If {company} is still hiring for the {role} role and you'd like to see the candidate's profile, just reply and I'll send it right over.

Best,
Susan
Susan · HireGen
susan@hiregen.co""",
    },
    "followup_5": {
        "subject": "Re: {company} — a candidate for your {short_role} opening",
        "body": """Hi {first_name},

I'll leave it here for now. If {company} is ever looking for strong talent down the road, I'd be glad to help.

Wishing you and the team all the best!

Best,
Susan
Susan · HireGen
susan@hiregen.co

P.S. You won't hear from me again on this one.""",
    },
}


# Multiple intro variants so a batch of outreach isn't byte-identical — identical
# templated mail is a bulk/spam signal. Each recipient gets a deterministic pick
# (based on their email) so previews and the actual send always match.
INTRO_SUBJECT_VARIANTS = [
    "{company} — a candidate for your {short_role} opening",
    "Candidate for {company}'s {short_role} role",
    "{short_role} at {company} — worth a quick look?",
    "A strong {short_role} candidate for {company}",
]

INTRO_BODY_VARIANTS = [
    """Hi {first_name},

I saw that {company} is hiring for a {role} — exciting to see the team growing.

I lead candidate placement at HireGen, and I have someone I genuinely think is worth a look for this role: they're actively interviewing, have directly relevant experience, and could ramp quickly.

Rather than send a résumé out of the blue, would you be open to a quick 15-minute call this week? And if the timing isn't right, no worries at all.

Thanks,
Susan
Susan · HireGen
susan@hiregen.co

P.S. If you'd prefer I don't follow up, just reply "no thanks" and I'll close this out.""",

    """Hi {first_name},

Saw that {company} has an opening for a {role} — congrats on the growth.

I run placements at HireGen and I'm working with someone who lines up well with this role: strong hands-on background, actively interviewing, and could get up to speed quickly.

Would a quick 15 minutes this week be worth it to see if they're a fit? No pressure at all if the timing's off.

Best,
Susan
Susan · HireGen
susan@hiregen.co

P.S. Not the right time? Just reply "no thanks" and I won't follow up.""",

    """Hi {first_name},

Noticed {company} is hiring a {role}, so I'll keep this short.

At HireGen I place engineers, and I have one candidate in particular who fits this role well — relevant experience, available now, and genuinely interested.

Open to a short call this week, or would a quick profile be easier to start? Whichever works for you.

Thanks,
Susan
Susan · HireGen
susan@hiregen.co

P.S. If you'd rather I not reach out, a quick "no thanks" and I'll close this out.""",
]


def get_gmail_service():
    return build("gmail", "v1", credentials=load_google_credentials())


def is_html(body: str) -> bool:
    """Detect if body contains HTML tags."""
    return bool(body and ("<p>" in body or "<b>" in body or "<a " in body or "<br" in body or "<ul>" in body))


def build_email(
    to_email: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    thread_id: str | None = None,
) -> dict:
    """Build the Gmail API send body.

    Generates our own RFC ``Message-ID`` so the caller knows it without an extra
    fetch (needed to thread follow-ups). When ``in_reply_to`` (the intro's
    Message-ID) is supplied, sets ``In-Reply-To``/``References`` so Gmail — and
    the recipient's mail client — thread the follow-up under the original.
    ``thread_id`` (Gmail's internal thread id) is attached to the send body so
    Gmail keeps it in the same conversation on our side too."""
    message = MIMEMultipart("alternative")
    message["to"] = to_email
    message["from"] = SENDER_EMAIL
    message["subject"] = subject

    # Sign each message with a Message-ID on the sender's domain so we can
    # reference it from later follow-ups.
    domain = SENDER_EMAIL.split("@")[-1] if "@" in SENDER_EMAIL else None
    msg_id = make_msgid(domain=domain)
    message["Message-ID"] = msg_id

    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to

    if is_html(body):
        # Send as HTML with a plain text fallback
        import re
        plain = re.sub(r"<[^>]+>", "", body).strip()
        message.attach(MIMEText(plain, "plain"))
        message.attach(MIMEText(body, "html"))
    else:
        message.attach(MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    return {"body": payload, "rfc_message_id": msg_id}


def send_email(
    to_email: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    thread_id: str | None = None,
) -> dict | None:
    """Send an email. Returns a dict with the Gmail message id, the thread id,
    and the RFC ``Message-ID`` header (store these to thread follow-ups), or
    ``None`` on failure.

    ``in_reply_to``/``thread_id`` come from the intro send and, when supplied,
    make this message land in the same conversation as the intro."""
    try:
        service = get_gmail_service()
        built = build_email(to_email, subject, body, in_reply_to, thread_id)
        sent = service.users().messages().send(userId="me", body=built["body"]).execute()
        return {
            "id": sent.get("id"),
            "thread_id": sent.get("threadId"),
            "rfc_message_id": built["rfc_message_id"],
        }
    except Exception as e:
        print(f"[Email] Failed to send to {to_email}: {e}")
        return None


def get_first_name(contact_name: str) -> str | None:
    """Extract first name from full name. Returns None if unavailable."""
    if not contact_name or not contact_name.strip():
        return None
    parts = contact_name.strip().split()
    return parts[0] if parts else None


def _short_role(role: str) -> str:
    """A clean, short version of the job title for subject lines — trims off
    everything after the first separator (' - ', '(', ',', '|') and caps length,
    so 'Sr ML Engineer - Fintech (100% Remote - USA)' -> 'Sr ML Engineer'."""
    if not role or not role.strip():
        return "open"
    r = role.strip()
    for sep in [" - ", " – ", " — ", " | ", " (", ", "]:
        idx = r.find(sep)
        if idx > 0:
            r = r[:idx]
    r = r.strip().rstrip(" -–—|(,")
    return (r[:44].rstrip() + "…") if len(r) > 45 else r


def render_template(template_key: str, lead: dict) -> tuple[str, str]:
    """Fill in template placeholders and return (subject, body).
    Always uses real first name — skips sending if name unavailable.
    Intro emails rotate through variants (deterministic per recipient) so a
    batch isn't identical."""
    first_name = get_first_name(lead.get("contact_name", ""))

    # Only use real first name — if unavailable, leave blank so caller can decide
    if not first_name:
        first_name = "there"  # last resort, dashboard should filter these out

    role = lead.get("job_title_hiring_for") or "software engineering"
    context = {
        "first_name": first_name,
        "company": lead.get("company_name", "your company"),
        "role": role,
        "short_role": _short_role(role),
    }

    if template_key == "intro":
        # Deterministic per-recipient variant pick (same email -> same variant).
        seed = int(hashlib.md5(
            (lead.get("contact_email") or lead.get("company_name") or "x").encode()
        ).hexdigest(), 16)
        subject_tmpl = INTRO_SUBJECT_VARIANTS[seed % len(INTRO_SUBJECT_VARIANTS)]
        body_tmpl = INTRO_BODY_VARIANTS[(seed // 13) % len(INTRO_BODY_VARIANTS)]
    else:
        template = EMAIL_TEMPLATES[template_key]
        subject_tmpl, body_tmpl = template["subject"], template["body"]

    subject = subject_tmpl.format(**context)
    body = body_tmpl.format(**context)
    return subject, body


FOLLOWUP_SEQUENCE = ["intro", "followup_1", "followup_2", "followup_3", "followup_4", "followup_5"]
