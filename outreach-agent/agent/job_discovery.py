"""
Job Discovery Module
--------------------
Primary source:  SerpAPI Google Jobs
Fallback sources (used automatically when SerpAPI quota is exhausted):
  1. LinkedIn Jobs  (guest API — no key required)
  2. The Muse API   (no key required)
  3. Adzuna API     (free tier — needs ADZUNA_APP_ID + ADZUNA_APP_KEY in .env)
"""

import os
import time
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

def _get_secret(key: str, default: str = "") -> str:
    """Read from env var first (local/Railway/Render), then Streamlit secrets (cloud).
    Only touches st.secrets when a secrets.toml exists, to avoid Streamlit rendering
    a 'No secrets files found' error banner."""
    val = os.getenv(key, "")
    if val:
        return val
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
    return default


def _serpapi_key() -> str:
    return _get_secret("SERPAPI_KEY")


def _adzuna_id() -> str:
    return _get_secret("ADZUNA_APP_ID")


def _adzuna_key() -> str:
    return _get_secret("ADZUNA_APP_KEY")


SERPAPI_KEY    = None  # loaded at runtime via _serpapi_key()
ADZUNA_APP_ID  = None  # loaded at runtime via _adzuna_id()
ADZUNA_APP_KEY = None  # loaded at runtime via _adzuna_key()
SERPAPI_URL    = "https://serpapi.com/search.json"

ALL_ROLES = [
    "Software Engineer",
    "Front-end Developer",
    "Back-end Developer",
    "Full-stack Developer",
    "AI Engineer",
    "Agent Engineer",
    "Machine Learning Engineer",
    "AI/ML Engineer",
    "Applied AI Engineer",
    "Forward Deployed Engineer",
]

ALL_LOCATIONS = [
    "Remote",
    "USA",
    "San Francisco",
    "San Francisco Bay Area",
    "California",
    "New York",
    "United States",
]

DEFAULT_ROLES     = ["Software Engineer", "Full-stack Developer", "AI Engineer"]
DEFAULT_LOCATIONS = ["United States", "Remote"]

# Muse API category mapping (closest matches to our roles)
MUSE_CATEGORY_MAP = {
    "software engineer":        "Software Engineer",
    "front-end developer":      "Software Engineer",
    "back-end developer":       "Software Engineer",
    "full-stack developer":     "Software Engineer",
    "ai engineer":              "Data Science",
    "agent engineer":           "Data Science",
    "machine learning engineer":"Data Science",
    "ai/ml engineer":           "Data Science",
    "applied ai engineer":      "Data Science",
    "forward deployed engineer":"Software Engineer",
}


# ─────────────────────────── SerpAPI ────────────────────────────────────────

_serpapi_quota_exhausted = False  # module-level flag; reset on each process start


def _search_serpapi(role: str, location: str = None, num: int = 10) -> list[dict]:
    """Returns raw SerpAPI jobs_results or raises on quota error."""
    global _serpapi_quota_exhausted
    if _serpapi_quota_exhausted:
        return []

    params = {
        "engine":   "google_jobs",
        "q":        f"{role} {location}" if location else role,
        "chips":    "date_posted:week",   # 'today' often returns 0 on free plans
        "num":      num,
        "api_key":  _serpapi_key(),
    }
    if location and location.lower() not in ("remote", "usa", "united states"):
        params["location"] = location

    resp = requests.get(SERPAPI_URL, params=params, timeout=15)

    if resp.status_code == 429:
        print("[Job Discovery] ⚠️  SerpAPI quota exhausted — switching to free fallbacks.")
        _serpapi_quota_exhausted = True
        return []

    resp.raise_for_status()
    data = resp.json()

    if "error" in data and "run out" in data["error"].lower():
        print("[Job Discovery] ⚠️  SerpAPI quota exhausted — switching to free fallbacks.")
        _serpapi_quota_exhausted = True
        return []

    return data.get("jobs_results", [])


def _parse_serpapi_job(job: dict, role: str, location: str) -> dict:
    return {
        "company_name":         job.get("company_name", "").strip(),
        "job_title_hiring_for": job.get("title", "").strip(),
        "job_url":              job.get("share_link") or (job.get("related_links") or [{}])[0].get("link", ""),
        "job_source":           job.get("via", "google_jobs").replace("via ", ""),
        "role_query":           role,
        "location_query":       location or "Any",
    }


# ─────────────────────────── LinkedIn (guest) ────────────────────────────────

_LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _search_linkedin(role: str, location: str = None, num: int = 10) -> list[dict]:
    """Scrape LinkedIn guest jobs search (no auth required)."""
    try:
        params = {
            "keywords": role,
            "f_TPR":    "r604800",  # last 7 days
            "start":    0,
        }
        if location and location.lower() not in ("remote", "usa"):
            params["location"] = location
        else:
            params["location"] = "United States"

        resp = requests.get(
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
            params=params,
            headers=_LINKEDIN_HEADERS,
            timeout=12,
        )
        if resp.status_code != 200:
            print(f"[Job Discovery] LinkedIn returned {resp.status_code} for '{role}'")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []
        for card in soup.find_all("li")[:num]:
            title_el   = card.find("h3", class_="base-search-card__title")
            company_el = card.find("h4", class_="base-search-card__subtitle")
            link_el    = card.find("a", class_="base-card__full-link")
            if not (title_el and company_el):
                continue
            jobs.append({
                "company_name":         company_el.get_text(strip=True),
                "job_title_hiring_for": title_el.get_text(strip=True),
                "job_url":              link_el["href"].split("?")[0] if link_el else "",
                "job_source":           "LinkedIn",
                "role_query":           role,
                "location_query":       location or "Any",
            })
        return jobs

    except Exception as e:
        print(f"[Job Discovery] LinkedIn error for '{role}': {e}")
        return []


# ─────────────────────────── The Muse API ────────────────────────────────────

def _search_muse(role: str, location: str = None, num: int = 10) -> list[dict]:
    """Query The Muse public jobs API (no key required)."""
    try:
        category = MUSE_CATEGORY_MAP.get(role.lower(), "Software Engineer")
        params   = {"category": category, "page": 0}
        if location and location.lower() not in ("remote", "usa", "united states"):
            params["location"] = location

        resp = requests.get(
            "https://www.themuse.com/api/public/jobs",
            params=params,
            timeout=10,
        )
        if not resp.ok:
            return []

        data = resp.json()
        jobs = []
        for j in data.get("results", [])[:num]:
            company = j.get("company", {}).get("name", "").strip()
            title   = j.get("name", "").strip()
            url     = j.get("refs", {}).get("landing_page", "")
            if company and title:
                jobs.append({
                    "company_name":         company,
                    "job_title_hiring_for": title,
                    "job_url":              url,
                    "job_source":           "The Muse",
                    "role_query":           role,
                    "location_query":       location or "Any",
                })
        return jobs

    except Exception as e:
        print(f"[Job Discovery] The Muse error for '{role}': {e}")
        return []


# ─────────────────────────── Adzuna API ──────────────────────────────────────

def _search_adzuna(role: str, location: str = None, num: int = 10) -> list[dict]:
    """Query Adzuna jobs API (free tier — register at developer.adzuna.com)."""
    if not _adzuna_id() or not _adzuna_key():
        return []

    try:
        params = {
            "app_id":          _adzuna_id(),
            "app_key":         _adzuna_key(),
            "results_per_page": num,
            "what":            role,
            "max_days_old":    7,
            "content-type":    "application/json",
        }
        if location and location.lower() not in ("remote", "usa", "united states"):
            params["where"] = location

        resp = requests.get(
            "https://api.adzuna.com/v1/api/jobs/us/search/1",
            params=params,
            timeout=10,
        )
        if not resp.ok:
            return []

        data = resp.json()
        jobs = []
        for j in data.get("results", [])[:num]:
            company = (j.get("company") or {}).get("display_name", "").strip()
            title   = j.get("title", "").strip()
            url     = j.get("redirect_url", "")
            if company and title:
                jobs.append({
                    "company_name":         company,
                    "job_title_hiring_for": title,
                    "job_url":              url,
                    "job_source":           "Adzuna",
                    "role_query":           role,
                    "location_query":       location or "Any",
                })
        return jobs

    except Exception as e:
        print(f"[Job Discovery] Adzuna error for '{role}': {e}")
        return []


# ─────────────────────────── Orchestrator ────────────────────────────────────

def _search_with_fallbacks(role: str, location: str, num: int) -> list[dict]:
    """
    Try SerpAPI first.  If quota is gone, run all free sources in parallel
    and merge results.
    """
    # 1. SerpAPI
    if _serpapi_key() and not _serpapi_quota_exhausted:
        results = _search_serpapi(role, location, num)
        if results:
            return [_parse_serpapi_job(j, role, location) for j in results]

    # 2. Free fallbacks
    print(f"[Job Discovery]   → Using free fallbacks for '{role}' / '{location}'")
    combined = []
    combined += _search_linkedin(role, location, num)
    combined += _search_muse(role, location, num)
    combined += _search_adzuna(role, location, num)
    return combined


def discover_jobs(
    roles: list[str] = None,
    locations: list[str] = None,
    max_per_combo: int = 10,
) -> list[dict]:
    if not roles:
        roles = DEFAULT_ROLES
    if not locations:
        locations = DEFAULT_LOCATIONS

    all_jobs      = []
    seen_companies = set()
    total_combos  = len(roles) * len(locations)
    count         = 0

    for role in roles:
        for location in locations:
            count += 1
            label = f"{role}" + (f" in {location}" if location else "")
            print(f"[Job Discovery] ({count}/{total_combos}) Searching: {label}")

            try:
                results = _search_with_fallbacks(role, location, max_per_combo)
                for job in results:
                    company = job.get("company_name", "").strip().lower()
                    if company and company not in seen_companies:
                        seen_companies.add(company)
                        all_jobs.append(job)
            except Exception as e:
                print(f"[Job Discovery] Error for '{label}': {e}")

            # Small delay to be polite to free APIs
            time.sleep(0.5)

    print(f"[Job Discovery] ✅ Found {len(all_jobs)} unique companies hiring.")
    return all_jobs
