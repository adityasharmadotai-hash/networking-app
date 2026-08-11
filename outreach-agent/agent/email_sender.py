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

I came across {company_pos} {short_role} opening{source_phrase} — exciting to see the team growing.

I lead candidate placement at HireGen, and I have someone I genuinely think is worth a look for this role: they're actively interviewing, have hands-on {specialty} experience, and could ramp quickly.

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

I came across {company_pos} {short_role} opening{source_phrase} — exciting to see the team growing.

I lead candidate placement at HireGen, and I have someone I genuinely think is worth a look for this role: they're actively interviewing, have hands-on {specialty} experience, and could ramp quickly.

Rather than send a résumé out of the blue, would you be open to a quick 15-minute call this week? And if the timing isn't right, no worries at all.

Thanks,
Susan
Susan · HireGen
susan@hiregen.co

P.S. If you'd prefer I don't follow up, just reply "no thanks" and I'll close this out.""",

    """Hi {first_name},

Saw {company_pos} {short_role} opening{source_phrase} — congrats on the growth.

I run placements at HireGen and I'm working with someone who lines up well with this role: a strong hands-on {specialty} background, actively interviewing, and could get up to speed quickly.

Would a quick 15 minutes this week be worth it to see if they're a fit? No pressure at all if the timing's off.

Best,
Susan
Susan · HireGen
susan@hiregen.co

P.S. Not the right time? Just reply "no thanks" and I won't follow up.""",

    """Hi {first_name},

Noticed {company_pos} {short_role} opening{source_phrase}, so I'll keep this short.

At HireGen I place engineers, and I have one candidate in particular who fits this role well — hands-on {specialty} experience, available now, and genuinely interested.

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


# Real, per-lead personalization from data we already store — no LLM, no guessing.
_KNOWN_SOURCES = {
    "linkedin": "LinkedIn", "indeed": "Indeed", "glassdoor": "Glassdoor",
    "greenhouse": "Greenhouse", "lever": "Lever", "ziprecruiter": "ZipRecruiter",
    "the muse": "The Muse", "themuse": "The Muse", "adzuna": "Adzuna",
    "wellfound": "Wellfound", "angellist": "Wellfound", "builtin": "Built In",
    "dice": "Dice", "monster": "Monster", "simplyhired": "SimplyHired",
}


def _job_source_phrase(source: str) -> str:
    """A natural ' on <Board>' clause when the source is a real, nameable job
    board — empty otherwise (so we never say 'on google_jobs'). Ready to append."""
    key = (source or "").lower().replace("via ", "").strip()
    for k, v in _KNOWN_SOURCES.items():
        if k in key:
            return f" on {v}"
    return ""


def _role_specialty(role: str) -> str:
    """Derive a short specialty from the job title so the copy can say 'hands-on
    back-end experience' instead of a generic filler. Falls back to a safe phrase."""
    r = (role or "").lower()
    checks = [
        (("front-end", "frontend", "front end"), "front-end"),
        (("back-end", "backend", "back end", "nodejs", "node.js"), "back-end"),
        (("full-stack", "fullstack", "full stack"), "full-stack"),
        (("machine learning", "ml engineer", "ml/", "/ml"), "machine learning"),
        (("data engineer", "data scientist", "data platform"), "data"),
        (("devops", "infrastructure", "platform engineer", "site relia", "sre"), "infrastructure"),
        (("mobile", "ios", "android"), "mobile"),
        (("ai engineer", "applied ai", "genai", "gen ai", "llm"), "AI"),
    ]
    for needles, label in checks:
        if any(n in r for n in needles):
            return label
    return "software engineering"


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
    company = lead.get("company_name", "your company")
    # Grammatical possessive: "Cerebras'" not "Cerebras's"; "Acme's".
    company_pos = company + ("'" if company.rstrip().lower().endswith("s") else "'s")
    context = {
        "first_name": first_name,
        "company": company,
        "company_pos": company_pos,
        "role": role,
        "short_role": _short_role(role),
        "specialty": _role_specialty(role),
        "source_phrase": _job_source_phrase(lead.get("job_source")),
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
