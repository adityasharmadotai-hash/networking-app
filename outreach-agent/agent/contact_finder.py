import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

SERPAPI_URL = "https://serpapi.com/search.json"
WIZA_BASE = "https://wiza.co/api"


def _get_secret(key: str) -> str:
    """Read from Streamlit secrets (cloud) or env var (local/Railway/Render)."""
    # Always check env var first — most reliable across all environments
    val = os.getenv(key, "")
    if val:
        return val
    # Then try Streamlit secrets — but only if a secrets.toml exists, otherwise
    # probing st.secrets makes Streamlit render a 'No secrets files found' banner.
    paths = [
        os.path.expanduser("~/.streamlit/secrets.toml"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     ".streamlit", "secrets.toml"),
    ]
    if any(os.path.exists(p) for p in paths):
        try:
            import streamlit as st
            val = st.secrets.get(key, "")
            if val:
                return val
        except Exception:
            pass
    return ""


def _wiza_key() -> str:
    return _get_secret("WIZA_API_KEY")


def _serpapi_key() -> str:
    return _get_secret("SERPAPI_KEY")


def _mask(key: str) -> str:
    """Mask a secret for safe display in the UI/logs."""
    if not key:
        return "❌ MISSING"
    if len(key) <= 8:
        return "✅ set (short)"
    return f"✅ {key[:4]}…{key[-4:]} (len {len(key)})"


def serpapi_account_info() -> dict:
    """Query SerpAPI's account endpoint for remaining monthly quota.
    Returns the raw JSON or an {'error': ...} dict."""
    key = _serpapi_key()
    if not key:
        return {"error": "SERPAPI_KEY not set"}
    try:
        r = requests.get("https://serpapi.com/account", params={"api_key": key}, timeout=15)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:150]}"}
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# Priority order of titles to search for at each company
TITLE_PRIORITY = [
    "Head of Talent",
    "Head of Recruiting",
    "Director of Talent Acquisition",
    "Technical Recruiter",
    "Recruiting Manager",
    "HR Manager",
    "Chief Technology Officer",
    "CTO",
    "CEO",
    "Chief Executive Officer",
    "VP Engineering",
]


def _find_linkedin_via_serpapi(query: str, log=print) -> str | None:
    """Find LinkedIn URL via SerpAPI Google engine (Bing ignores quoted phrases — useless for this).
    `log` is a callback (defaults to print) so the dashboard can surface detail in the UI."""
    key = _serpapi_key()
    if not key:
        log("    ⚠️ SerpAPI key MISSING — cannot search. Set SERPAPI_KEY in Streamlit secrets.")
        return None
    try:
        params = {"engine": "google", "q": query, "num": 10, "api_key": key}
        r = requests.get(SERPAPI_URL, params=params, timeout=20)
        if r.status_code == 429:
            log("    ⚠️ SerpAPI HTTP 429 — monthly quota / rate limit exhausted.")
            return None
        if r.status_code != 200:
            log(f"    ⚠️ SerpAPI HTTP {r.status_code}: {r.text[:150]}")
            return None
        data = r.json()
        if "error" in data:
            log(f"    ⚠️ SerpAPI error: {data['error']}")
            return None
        organic = data.get("organic_results", [])
        in_links = [res.get("link", "") for res in organic if "linkedin.com/in/" in res.get("link", "")]
        log(f"    SerpAPI: {len(organic)} organic results, {len(in_links)} linkedin.com/in")
        if in_links:
            return in_links[0].split("?")[0]
        # No profile links — show what DID come back so we can see why
        if organic:
            sample = " | ".join(res.get("link", "")[:70] for res in organic[:3])
            log(f"      ↳ top results were: {sample}")
    except Exception as e:
        log(f"    ⚠️ SerpAPI exception: {e}")
    return None


def _find_linkedin_via_google_cse(query: str, log=print) -> str | None:
    """Fallback: Google Custom Search API (free: 100 queries/day)."""
    api_key = _get_secret("GOOGLE_CSE_API_KEY")
    cx      = _get_secret("GOOGLE_CSE_ID")
    if not api_key or not cx:
        log("    ⚠️ Google CSE not configured (GOOGLE_CSE_API_KEY / GOOGLE_CSE_ID missing) — no fallback.")
        return None
    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": api_key, "cx": cx, "q": query, "num": 3},
            timeout=12,
        )
        if not r.ok:
            log(f"    ⚠️ Google CSE error: {r.status_code} {r.text[:100]}")
            return None
        items = r.json().get("items", [])
        for item in items:
            link = item.get("link", "")
            if "linkedin.com/in/" in link:
                log(f"    ✅ Google CSE found: {link}")
                return link.split("?")[0]
        log(f"    Google CSE: {len(items)} results, 0 linkedin.com/in")
    except Exception as e:
        log(f"    ⚠️ Google CSE exception: {e}")
    return None


def find_linkedin_url(company_name: str, title: str, log=print) -> str | None:
    """Find a LinkedIn profile URL — tries two query styles, then Google CSE."""
    queries = [
        f'site:linkedin.com/in "{title}" "{company_name}"',     # path-level x-ray: profiles only
        f'site:linkedin.com/in {title} {company_name}',         # looser: drop exact-phrase quotes
    ]

    for query in queries:
        url = _find_linkedin_via_serpapi(query, log=log)
        if url:
            return url

    # Final fallback: Google CSE
    log(f"    SerpAPI found nothing — trying Google CSE fallback")
    return _find_linkedin_via_google_cse(f'"{title}" "{company_name}" linkedin.com/in', log=log)


# ── Hunter.io fallback (finds email directly by company domain) ───────────────

def _guess_domain(company_name: str) -> str:
    """Best-effort company domain guess."""
    import re
    slug = re.sub(r"[^a-z0-9]", "", company_name.lower().strip())
    return f"{slug}.com"


def _hunter_domain_search(company_name: str) -> dict | None:
    """
    Use Hunter.io to find a recruiter/HR email at a company directly.
    Requires HUNTER_API_KEY in env/secrets (free tier: 25 searches/month).
    Sign up free at https://hunter.io
    """
    hunter_key = _get_secret("HUNTER_API_KEY")
    if not hunter_key:
        return None

    domain = _guess_domain(company_name)
    RECRUITER_DEPTS = ["executive", "hr", "management"]

    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain":       domain,
                "api_key":      hunter_key,
                "limit":        10,
                "seniority":    "senior,executive",
            },
            timeout=12,
        )
        if not r.ok:
            return None

        data    = r.json().get("data", {})
        emails  = data.get("emails", [])

        # Priority: HR/recruiting titles first
        PRIORITY_KEYWORDS = [
            "talent", "recruit", "hr", "human resource",
            "cto", "ceo", "vp engineering", "founder",
        ]

        def score(e):
            title_lower = (e.get("position") or "").lower()
            for i, kw in enumerate(PRIORITY_KEYWORDS):
                if kw in title_lower:
                    return i
            return 99

        emails = [e for e in emails if e.get("value") and e.get("type") == "professional"]
        if not emails:
            return None

        best = sorted(emails, key=score)[0]
        first = best.get("first_name", "")
        last  = best.get("last_name", "")
        return {
            "contact_name":         f"{first} {last}".strip(),
            "contact_title":        best.get("position", ""),
            "contact_email":        best.get("value", ""),
            "contact_linkedin_url": best.get("linkedin", ""),
        }

    except Exception as e:
        print(f"[Contact Finder] Hunter.io error for '{company_name}': {e}")
    return None


def start_wiza_reveal(linkedin_url: str, log=print) -> str | None:
    """Submit a LinkedIn URL to Wiza and return the reveal ID."""
    if not _wiza_key():
        log("    ⚠️ Wiza key MISSING — cannot reveal email. Set WIZA_API_KEY in Streamlit secrets.")
        return None
    headers = {
        "Authorization": f"Bearer {_wiza_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "individual_reveal": {
            "profile_url": linkedin_url,
        },
        "enrichment_level": "partial",
        "email_options": {
            "accept_work": True,
            "accept_personal": False,
        },
    }
    try:
        r = requests.post(f"{WIZA_BASE}/individual_reveals", json=payload, headers=headers, timeout=15)
        if r.status_code in (200, 201):
            data = r.json()
            reveal_id = data.get("id") or data.get("data", {}).get("id")
            return str(reveal_id) if reveal_id else None
        else:
            log(f"    ⚠️ Wiza reveal error: HTTP {r.status_code} {r.text[:200]}")
    except Exception as e:
        log(f"    ⚠️ Wiza submit error: {e}")
    return None


def poll_wiza_reveal(reveal_id: str, max_wait: int = 60) -> dict | None:
    """Poll Wiza until the reveal is complete or timeout. Returns contact data."""
    headers = {"Authorization": f"Bearer {_wiza_key()}"}
    start = time.time()

    while time.time() - start < max_wait:
        try:
            r = requests.get(f"{WIZA_BASE}/individual_reveals/{reveal_id}", headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                reveal = data.get("data", data)
                status = reveal.get("status", "")

                if status == "finished":
                    # Try top-level email field first, then emails array
                    email = None
                    if reveal.get("email") and reveal.get("email_type") == "work" and reveal.get("email_status") == "valid":
                        email = reveal["email"]
                    else:
                        emails = reveal.get("emails", [])
                        work_emails = [e for e in emails if e.get("type") == "work" and e.get("status") == "valid"]
                        if work_emails:
                            email = work_emails[0]["email"]

                    if email:
                        return {
                            "contact_name": reveal.get("name", "").strip(),
                            "contact_title": reveal.get("title", ""),
                            "contact_email": email,
                            "contact_linkedin_url": reveal.get("linkedin_profile_url", ""),
                        }
                    return None

                elif status in ("failed", "error", "complete"):
                    return None

            time.sleep(5)

        except Exception as e:
            print(f"[Contact Finder] Wiza poll error: {e}")
            time.sleep(5)

    print(f"[Contact Finder] Wiza timed out for reveal {reveal_id}")
    return None


def prospect_contact(company_name: str) -> dict | None:
    """Find best contact: LinkedIn URL via SerpAPI or Google CSE → Wiza for email."""
    for title in TITLE_PRIORITY:
        print(f"[Contact Finder] Searching LinkedIn: '{title}' at '{company_name}'")
        linkedin_url = find_linkedin_url(company_name, title)

        if not linkedin_url:
            continue

        print(f"[Contact Finder] Found LinkedIn: {linkedin_url}")
        reveal_id = start_wiza_reveal(linkedin_url)

        if not reveal_id:
            continue

        print(f"[Contact Finder] Wiza reveal started (id: {reveal_id}), waiting for email...")
        contact = poll_wiza_reveal(reveal_id, max_wait=420)

        if contact:
            print(f"[Contact Finder] ✅ Got email for {contact['contact_name']} at {company_name}")
            return contact

    print(f"[Contact Finder] No contact found for: {company_name}")
    return None


def enrich_leads(jobs: list[dict]) -> list[dict]:
    """Add contact info to each job/company."""
    enriched = []
    for job in jobs:
        company = job["company_name"]
        print(f"\n[Contact Finder] Looking up contact at: {company}")
        contact = prospect_contact(company)
        if contact:
            job.update(contact)
        else:
            job["status"] = "skipped"
        enriched.append(job)
    return enriched
