import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

WIZA_API_KEY = os.getenv("WIZA_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search.json"
WIZA_BASE = "https://wiza.co/api"

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


def find_linkedin_url(company_name: str, title: str) -> str | None:
    """Use SerpAPI to find a LinkedIn profile URL for a given title at a company."""
    query = f'site:linkedin.com/in "{title}" "{company_name}"'
    params = {
        "engine": "google",
        "q": query,
        "num": 3,
        "api_key": SERPAPI_KEY,
    }
    try:
        r = requests.get(SERPAPI_URL, params=params, timeout=15)
        r.raise_for_status()
        results = r.json().get("organic_results", [])
        for result in results:
            link = result.get("link", "")
            if "linkedin.com/in/" in link:
                return link
    except Exception as e:
        print(f"[Contact Finder] SerpAPI error for '{title}' at '{company_name}': {e}")
    return None


def start_wiza_reveal(linkedin_url: str) -> str | None:
    """Submit a LinkedIn URL to Wiza and return the reveal ID."""
    headers = {
        "Authorization": f"Bearer {WIZA_API_KEY}",
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
    headers = {"Authorization": f"Bearer {WIZA_API_KEY}"}
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
    """Find the best contact at a company using SerpAPI + Wiza."""
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
            print(f"[Contact Finder] Got email for {contact['contact_name']} at {company_name}")
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
