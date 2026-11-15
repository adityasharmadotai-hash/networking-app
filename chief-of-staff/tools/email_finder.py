"""Find and verify email addresses.

With HUNTER_API_KEY set, uses Hunter.io (verified addresses + confidence scores).
Without it, falls back to common corporate patterns + an MX check on the domain,
and clearly labels the results as unverified guesses.
"""
import re
import unicodedata

import requests

from core import config

HUNTER = "https://api.hunter.io/v2"


def _clean(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def _split_name(full_name):
    parts = [p for p in re.split(r"\s+", (full_name or "").strip()) if p]
    if not parts:
        return "", ""
    return parts[0], parts[-1] if len(parts) > 1 else ""


def _normalize_domain(domain):
    d = (domain or "").strip().lower()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    return d[4:] if d.startswith("www.") else d


def _has_mx(domain):
    try:
        import dns.resolver
        return len(dns.resolver.resolve(domain, "MX", lifetime=6)) > 0
    except ImportError:
        return None
    except Exception:
        return False


def _hunter(path, **params):
    params["api_key"] = config.HUNTER_API_KEY
    r = requests.get(f"{HUNTER}/{path}", params=params, timeout=20)
    data = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(f"Hunter {path} HTTP {r.status_code}: {data.get('errors') or r.text[:200]}")
    return data.get("data") or {}


def find_email(full_name: str, domain: str = "", company: str = "") -> dict:
    first, last = _split_name(full_name)
    domain = _normalize_domain(domain)
    if not domain and not company:
        return {"error": "Provide the company domain (preferred) or company name."}

    if config.HUNTER_API_KEY:
        params = {"first_name": first, "last_name": last}
        if domain:
            params["domain"] = domain
        else:
            params["company"] = company
        d = _hunter("email-finder", **params)
        return {
            "source": "hunter.io",
            "email": d.get("email"),
            "confidence_score": d.get("score"),
            "verification": (d.get("verification") or {}).get("status"),
            "position": d.get("position"),
            "linkedin_url": d.get("linkedin_url"),
            "domain": d.get("domain") or domain,
        }

    if not domain:
        return {"error": "No HUNTER_API_KEY configured, so a domain is required. Look up the company website first."}
    f, l = _clean(first), _clean(last)
    patterns = [f"{f}.{l}", f"{f}", f"{f[:1]}{l}", f"{f}{l}", f"{f}_{l}", f"{f}{l[:1]}", f"{l}.{f}", f"{f[:1]}.{l}"]
    candidates = []
    for p in patterns:
        if p and not p.startswith(".") and not p.endswith(".") and f"{p}@{domain}" not in candidates:
            candidates.append(f"{p}@{domain}")
    return {
        "source": "pattern-guess (unverified)",
        "domain_accepts_mail": _has_mx(domain),
        "candidates_most_likely_first": candidates,
        "note": "These are guesses from common patterns. Prefer an address found publicly via web_research/fetch_url, "
                "or set HUNTER_API_KEY for verified results. Tell the user the address is unverified.",
    }


def verify_email(email: str) -> dict:
    email = (email or "").strip().lower()
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)+$", email):
        return {"email": email, "status": "invalid_syntax"}
    if config.HUNTER_API_KEY:
        d = _hunter("email-verifier", email=email)
        return {"email": email, "status": d.get("status"), "score": d.get("score"), "source": "hunter.io"}
    domain = email.split("@")[1]
    mx = _has_mx(domain)
    return {"email": email, "status": "domain_accepts_mail" if mx else ("no_mx_record" if mx is False else "unknown"),
            "source": "mx-check (mailbox not verified)"}


def company_email_directory(domain: str, department: str = "", limit: int = 10) -> dict:
    """People + emails Hunter knows at a company domain."""
    if not config.HUNTER_API_KEY:
        return {"error": "Requires HUNTER_API_KEY. Use web_research to find people at the company instead."}
    params = {"domain": _normalize_domain(domain), "limit": min(int(limit or 10), 100)}
    if department:
        params["department"] = department
    d = _hunter("domain-search", **params)
    return {
        "organization": d.get("organization"),
        "pattern": d.get("pattern"),
        "people": [
            {"name": f"{e.get('first_name') or ''} {e.get('last_name') or ''}".strip(), "email": e.get("value"),
             "position": e.get("position"), "department": e.get("department"),
             "confidence": e.get("confidence"), "linkedin": e.get("linkedin")}
            for e in d.get("emails", [])
        ],
    }
