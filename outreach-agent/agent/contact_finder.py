import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

SERPAPI_URL = "https://serpapi.com/search.json"
WIZA_BASE = "https://wiza.co/api"


def _get_secret(key: str) -> str:
    """Read from Streamlit secrets (cloud) or env var (local/Railway)."""
    # Always check env var first — most reliable across all environments
    val = os.getenv(key, "")
    if val:
        return val
    # Then try Streamlit secrets
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


def _find_linkedin_via_serpapi(query: str) -> str | None:
    """Find LinkedIn URL via SerpAPI Google search."""
    if not _serpapi_key():
        return None
    try:
        params = {"engine": "google", "q": query, "num": 3, "api_key": _serpapi_key()}
        r = requests.get(SERPAPI_URL, params=params, timeout=20)
        if r.status_code == 429:
            print("[Contact Finder] SerpAPI quota exhausted.")
            return None
        data = r.json()
        if "error" in data:
            print(f"[Contact Finder] SerpAPI error: {data['error']}")
            return None
        for result in data.get("organic_results", []):
            link = result.get("link", "")
            if "linkedin.com/in/" in link:
                return link
    except Exception as e:
        print(f"[Contact Finder] SerpAPI error: {e}")
    return None


def _find_linkedin_via_google_cse(query: str) -> str | None:
    """Fallback: Google Custom Search API (free: 100 queries/day)."""
    api_key = _get_secret("GOOGLE_CSE_API_KEY")
    cx      = _get_secret("GOOGLE_CSE_ID")
    if not api_key or not cx:
        return None
    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": api_key, "cx": cx, "q": query, "num": 3},
            timeout=12,
        )
        if not r.ok:
            print(f"[Contact Finder] Google CSE error: {r.status_code} {r.text[:100]}")
            return None
        for item in r.json().get("items", []):
            link = item.get("link", "")
            if "linkedin.com/in/" in link:
                return link.split("?")[0]
    except Exception as e:
        print(f"[Contact Finder] Google CSE error: {e}")
    return None


def find_linkedin_url(company_name: str, title: str) -> str | None:
    """Find a LinkedIn profile URL — SerpAPI first, Google CSE as fallback."""
    query = f'site:linkedin.com/in "{title}" "{company_name}"'

    # 1. SerpAPI
    url = _find_linkedin_via_serpapi(query)
    if url:
        return url

    # 2. Google Custom Search API (free 100/day fallback)
    print(f"[Contact Finder] SerpAPI unavailable — trying Google CSE for '{title}' at '{company_name}'")
    return _find_linkedin_via_google_cse(query)


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


def start_wiza_reveal(linkedin_url: str) -> str | None:
    """Submit a LinkedIn URL to Wiza and return the reveal ID."""
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
            print(f"[Contact Finder] Wiza reveal error: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[Contact Finder] Wiza submit error: {e}")
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
