"""
Wizard Session Store
--------------------
Streamlit throws away `st.session_state` whenever the browser reconnects with a
new session id - which happens on a refresh, a laptop waking from sleep, an idle
websocket timeout, or the Cloud container recycling. That wiped every discovered
job, dedup result and contact lookup, forcing a full re-run (and re-spending
SerpAPI / Wiza quota).

This module parks the wizard state outside the Streamlit session so it can be
restored. Supabase is the primary store (survives container restarts); a local
JSON file is the fallback when Supabase is unreachable.

Requires `supabase/wizard_sessions.sql` to have been applied.
"""

import os
import json
import time
import tempfile

TABLE = "wizard_sessions"

# Sessions older than this are dropped on the next write, so the table does not
# grow without bound.
TTL_DAYS = int(os.getenv("WIZARD_SESSION_TTL_DAYS", "14"))

_LOCAL_DIR = os.path.join(tempfile.gettempdir(), "hiregen_sessions")


# ── local fallback ────────────────────────────────────────────────────────────

def _local_path(sid: str) -> str:
    safe = "".join(c for c in sid if c.isalnum() or c in "-_")[:64]
    return os.path.join(_LOCAL_DIR, f"{safe}.json")


def _local_save(sid: str, state: dict) -> None:
    try:
        os.makedirs(_LOCAL_DIR, exist_ok=True)
        with open(_local_path(sid), "w", encoding="utf-8") as fh:
            json.dump({"saved_at": time.time(), "state": state}, fh)
    except Exception as e:
        print(f"[SessionStore] local save failed: {e}")


def _local_load(sid: str) -> dict | None:
    try:
        path = _local_path(sid)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > TTL_DAYS * 86400:
            return None
        with open(path, encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("state")
    except Exception as e:
        print(f"[SessionStore] local load failed: {e}")
        return None


def _local_clear(sid: str) -> None:
    try:
        path = _local_path(sid)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ── public API ────────────────────────────────────────────────────────────────

def save_state(supabase, sid: str, state: dict) -> bool:
    """Persist `state` for `sid`. Returns True if it reached Supabase.

    Always writes the local copy too, so a Supabase outage still survives a
    plain page refresh.
    """
    if not sid:
        return False

    _local_save(sid, state)

    if supabase is None:
        return False
    try:
        from datetime import datetime, timedelta, timezone
        supabase.table(TABLE).upsert({
            "id": sid,
            "state": state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        # Opportunistic cleanup of expired rows (cheap, once per save).
        cutoff = (datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)).isoformat()
        supabase.table(TABLE).delete().lt("updated_at", cutoff).execute()
        return True
    except Exception as e:
        print(f"[SessionStore] Supabase save failed ({e}) - local copy kept.")
        return False


def load_state(supabase, sid: str) -> dict | None:
    """Restore state for `sid`, preferring Supabase over the local copy."""
    if not sid:
        return None

    if supabase is not None:
        try:
            rows = supabase.table(TABLE).select("state").eq("id", sid) \
                .limit(1).execute().data or []
            if rows and rows[0].get("state"):
                return rows[0]["state"]
        except Exception as e:
            print(f"[SessionStore] Supabase load failed ({e}) - trying local copy.")

    return _local_load(sid)


def clear_state(supabase, sid: str) -> None:
    """Forget a session (used on logout and on 'Start a New Outreach Run')."""
    if not sid:
        return
    _local_clear(sid)
    if supabase is None:
        return
    try:
        supabase.table(TABLE).delete().eq("id", sid).execute()
    except Exception as e:
        print(f"[SessionStore] Supabase clear failed: {e}")
