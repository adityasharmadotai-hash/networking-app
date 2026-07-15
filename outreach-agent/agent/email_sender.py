import os
import base64
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_token_path() -> str:
    """
    Returns a path to a valid gmail_token pickle file.
    On Streamlit Cloud, loads the token from st.secrets (GMAIL_TOKEN_B64).
    Locally, uses the file on disk.
    """
    # 1. Plain env var — works on Railway and any cloud server
    token_b64 = os.getenv("GMAIL_TOKEN_B64", "")
    if token_b64:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
        tmp.write(base64.b64decode(token_b64))
        tmp.flush()
        tmp.close()
        return tmp.name

    # 2. Streamlit secrets — works on Streamlit Cloud
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

    # 3. Fall back to local file (development)
    return GMAIL_TOKEN_FILE

EMAIL_TEMPLATES = {
    "intro": {
        "subject": "Quick intro — candidates for your {role} opening",
        "body": """Hi {first_name},

I noticed that {company} is hiring for a {role} — great timing!

I work with HireGen, and we have a strong candidate who would be a great fit for this role. They're actively looking and have relevant experience that aligns well with what you're hiring for.

Would you be open to a quick 15-minute call to hear more? Happy to work around your schedule.

Thanks,
Susan
Susan | HireGen
susan@hiregen.co""",
    },
    "followup_1": {
        "subject": "Re: Quick intro — candidates for your {role} opening",
        "body": """Hi {first_name},

Just wanted to follow up on my previous email. We still have a strong candidate who could be a great fit for your {role} role at {company}.

Would you have 15 minutes this week for a quick call?

Thanks,
Susan
Susan | HireGen
susan@hiregen.co""",
    },
    "followup_2": {
        "subject": "Re: Quick intro — candidates for your {role} opening",
        "body": """Hi {first_name},

I know you're busy, so I'll keep this short — our candidate is still available and very much interested in a role like the one {company} is hiring for.

Happy to send over a brief profile if that would make it easier to evaluate.

Best,
Susan
Susan | HireGen
susan@hiregen.co""",
    },
    "followup_3": {
        "subject": "Re: Quick intro — candidates for your {role} opening",
        "body": """Hi {first_name},

Still thinking this could be a great fit for both sides. Our candidate has a strong background in exactly what {company} is looking for.

Let me know if you'd like me to send a profile or hop on a quick call.

Thanks,
Susan
Susan | HireGen
susan@hiregen.co""",
    },
    "followup_4": {
        "subject": "Re: Quick intro — candidates for your {role} opening",
        "body": """Hi {first_name},

Last follow-up on this — I don't want to take up more of your time if the timing isn't right.

If you're still actively hiring for the {role} position and would like to see our candidate's profile, just reply and I'll send it right over.

Best,
Susan
Susan | HireGen
susan@hiregen.co""",
    },
    "followup_5": {
        "subject": "Re: Quick intro — candidates for your {role} opening",
        "body": """Hi {first_name},

I'll leave it here for now — if you ever need strong engineering talent in the future, please don't hesitate to reach out.

Wishing {company} all the best!

Susan
Susan | HireGen
susan@hiregen.co""",
    },
}


def get_gmail_service():
    creds = None
    token_path = _get_token_path()

    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return build("gmail", "v1", credentials=creds)


def is_html(body: str) -> bool:
    """Detect if body contains HTML tags."""
    return bool(body and ("<p>" in body or "<b>" in body or "<a " in body or "<br" in body or "<ul>" in body))


def build_email(to_email: str, subject: str, body: str) -> dict:
    message = MIMEMultipart("alternative")
    message["to"] = to_email
    message["from"] = SENDER_EMAIL
    message["subject"] = subject

    if is_html(body):
        # Send as HTML with a plain text fallback
        import re
        plain = re.sub(r"<[^>]+>", "", body).strip()
        message.attach(MIMEText(plain, "plain"))
        message.attach(MIMEText(body, "html"))
    else:
        message.attach(MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


def send_email(to_email: str, subject: str, body: str) -> str | None:
    """Send an email and return the Gmail message ID."""
    try:
        service = get_gmail_service()
        message = build_email(to_email, subject, body)
        sent = service.users().messages().send(userId="me", body=message).execute()
        return sent.get("id")
    except Exception as e:
        print(f"[Email] Failed to send to {to_email}: {e}")
        return None


def get_first_name(contact_name: str) -> str | None:
    """Extract first name from full name. Returns None if unavailable."""
    if not contact_name or not contact_name.strip():
        return None
    parts = contact_name.strip().split()
    return parts[0] if parts else None


def render_template(template_key: str, lead: dict) -> tuple[str, str]:
    """Fill in template placeholders and return (subject, body).
    Always uses real first name — skips sending if name unavailable."""
    template = EMAIL_TEMPLATES[template_key]
    first_name = get_first_name(lead.get("contact_name", ""))

    # Only use real first name — if unavailable, leave blank so caller can decide
    if not first_name:
        first_name = "there"  # last resort, dashboard should filter these out

    context = {
        "first_name": first_name,
        "company": lead.get("company_name", "your company"),
        "role": lead.get("job_title_hiring_for", "software engineering"),
    }
    subject = template["subject"].format(**context)
    body = template["body"].format(**context)
    return subject, body


FOLLOWUP_SEQUENCE = ["intro", "followup_1", "followup_2", "followup_3", "followup_4", "followup_5"]
