"""
Pre-send email validation.
-------------------------
Rejects malformed addresses cheaply (always on, free), and *optionally* verifies
real deliverability via a remote provider when explicitly enabled. Remote
verification is OFF by default (set VERIFY_EMAILS_REMOTE=true to turn it on) so it
never silently burns a metered API quota — syntax validation runs regardless.

Used as a last-line gate before every send, and at enrichment time so bad
addresses never enter the queue in the first place.
"""

import os
import re
import requests

# Deliberately conservative: one @, a non-empty local part, and a domain with at
# least one dot and no leading/trailing hyphen. Catches mangled extractions
# (empty, spaces, double dots, "@gmail", trailing dot) without over-rejecting.
_SYNTAX_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def is_valid_syntax(email: str) -> bool:
    e = (email or "").strip()
    if not e or len(e) > 254 or e.count("@") != 1:
        return False
    local, _, domain = e.partition("@")
    if not local or not domain or ".." in e:
        return False
    if local.startswith(".") or local.endswith("."):
        return False
    if domain.startswith("-") or domain.endswith("-") or "." not in domain:
        return False
    return bool(_SYNTAX_RE.match(e))


def _remote_status(email: str) -> str | None:
    """Deliverability status via Hunter's email-verifier, or None if unavailable.
    Returns e.g. 'deliverable' | 'undeliverable' | 'risky' | 'unknown'."""
    key = os.getenv("HUNTER_API_KEY", "")
    if not key:
        return None
    try:
        r = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": key},
            timeout=12,
        )
        if not r.ok:
            return None
        return ((r.json() or {}).get("data") or {}).get("status")
    except Exception:
        return None


def validate_email(email: str) -> tuple[bool, str]:
    """Return (is_sendable, reason).

    Always syntax-checks. Only calls a remote verifier when
    VERIFY_EMAILS_REMOTE=true AND a provider key (HUNTER_API_KEY) is configured —
    and even then only *undeliverable* is rejected ('risky'/'unknown' are allowed
    through, since verifiers over-flag catch-all domains)."""
    e = (email or "").strip().lower()
    if not is_valid_syntax(e):
        return False, "malformed"
    if os.getenv("VERIFY_EMAILS_REMOTE", "false").lower() == "true":
        if _remote_status(e) == "undeliverable":
            return False, "verifier: undeliverable"
    return True, "ok"
