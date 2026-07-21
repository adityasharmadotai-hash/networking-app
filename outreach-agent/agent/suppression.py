"""
Suppression list — emails that must NEVER be contacted again (unsubscribes,
opt-outs). Kept in its own `unsubscribes` table so it survives lead resets,
and checked before every intro and follow-up send.

Table (run supabase/unsubscribes.sql once):
    create table if not exists unsubscribes (
        email text primary key,
        reason text,
        created_at timestamptz default now()
    );
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def _sb():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _norm(email: str) -> str:
    return (email or "").strip().lower()


def record_unsubscribe(email: str, reason: str = "reply") -> None:
    """Add an email to the permanent suppression list (idempotent)."""
    email = _norm(email)
    if not email:
        return
    try:
        _sb().table("unsubscribes").upsert(
            {"email": email, "reason": reason}, on_conflict="email"
        ).execute()
        print(f"[Suppression] Unsubscribed {email} ({reason}) — will never be contacted again.")
    except Exception as e:
        print(f"[Suppression] Could not record unsubscribe for {email}: {e}")


def get_unsubscribed_emails() -> set[str]:
    """Return the full set of suppressed emails (lowercased)."""
    try:
        rows = _sb().table("unsubscribes").select("email").execute().data or []
        return {_norm(r["email"]) for r in rows if r.get("email")}
    except Exception as e:
        print(f"[Suppression] Could not load suppression list: {e}")
        return set()


def is_unsubscribed(email: str) -> bool:
    """True if this email is on the suppression list."""
    email = _norm(email)
    if not email:
        return False
    try:
        r = _sb().table("unsubscribes").select("email").eq("email", email).limit(1).execute()
        return bool(r.data)
    except Exception:
        return False
