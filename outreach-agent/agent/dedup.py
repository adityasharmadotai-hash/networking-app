import os
import re
import base64
import pickle
import tempfile
import gspread
from google.auth.transport.requests import Request
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMAIL_TOKEN_FILE = os.path.join(_BASE_DIR, os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json"))


def _get_token_path() -> str:
    """Load Gmail token from env var (Railway), Streamlit secrets (cloud), or local file."""
    # 1. Plain env var — Railway / any server
    token_b64 = os.getenv("GMAIL_TOKEN_B64", "")
    if token_b64:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
        tmp.write(base64.b64decode(token_b64))
        tmp.flush()
        tmp.close()
        return tmp.name

    # 2. Streamlit secrets
    try:
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


def normalize(name: str) -> str:
    """Lowercase, strip punctuation for fuzzy company name matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())


def get_existing_clients() -> set[str]:
    """Fetch company names from the Google Sheet using existing Gmail OAuth token."""
    try:
        token_path = _get_token_path()
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        records = sheet.get_all_records()

        clients = set()
        for row in records:
            # Try common column names for company name
            name = (
                row.get("Company")
                or row.get("Company Name")
                or row.get("company_name")
                or row.get("Employer")
                or ""
            )
            if name:
                clients.add(normalize(str(name)))

        print(f"[Dedup] Loaded {len(clients)} existing clients from Google Sheet.")
        return clients

    except Exception as e:
        print(f"[Dedup] Could not load Google Sheet: {e}")
        return set()


def get_already_contacted(days: int = 30) -> set[str]:
    """Fetch companies contacted in the last N days (default 30)."""
    try:
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        response = supabase.table("leads") \
            .select("company_name, last_contacted_at") \
            .gte("last_contacted_at", cutoff) \
            .execute()
        contacted = {normalize(row["company_name"]) for row in response.data}
        print(f"[Dedup] Found {len(contacted)} companies contacted in the last {days} days.")
        return contacted
    except Exception as e:
        print(f"[Dedup] Could not load Supabase leads: {e}")
        return set()


def filter_leads(leads: list[dict]) -> list[dict]:
    """Remove leads that are existing clients or already contacted."""
    existing_clients = get_existing_clients()
    already_contacted = get_already_contacted()
    blocked = existing_clients | already_contacted

    filtered = []
    skipped = 0
    for lead in leads:
        key = normalize(lead.get("company_name", ""))
        if key in blocked:
            print(f"[Dedup] Skipping {lead['company_name']} — already a client or contacted.")
            skipped += 1
        else:
            filtered.append(lead)

    print(f"[Dedup] {len(filtered)} leads passed dedup ({skipped} skipped).")
    return filtered
