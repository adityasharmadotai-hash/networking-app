"""Web research via Gemini + Google Search grounding, and page fetching."""
import re

import requests
from google.genai import types

from core import config
from core.gemini import client

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_JUNK_EMAIL = ("example.com", "sentry.io", "wixpress.com", ".png", ".jpg", ".gif", ".webp", "domain.com")


def web_research(query: str, focus: str = "") -> dict:
    prompt = (
        "Research the following using Google Search. Be specific and factual: give names, titles, "
        "companies, websites/domains, LinkedIn URLs, locations, funding, headcount, and any publicly "
        "listed contact details you find. Say clearly when something could not be verified.\n\n"
        f"Query: {query}"
    )
    if focus:
        prompt += f"\nFocus on: {focus}"
    resp = client().models.generate_content(
        model=config.RESEARCH_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
    )
    sources = []
    try:
        gm = resp.candidates[0].grounding_metadata
        for ch in (gm.grounding_chunks or []):
            if ch.web:
                sources.append({"title": ch.web.title, "url": ch.web.uri})
    except Exception:
        pass
    return {"findings": resp.text or "", "sources": sources[:15]}


def fetch_url(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (research assistant)"})
    html = r.text
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    mailtos = re.findall(r'mailto:([^"\'?>\s]+)', html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    emails = sorted({e.lower() for e in EMAIL_RE.findall(html) + mailtos
                     if not any(j in e.lower() for j in _JUNK_EMAIL)})
    return {"url": r.url, "status": r.status_code, "emails_on_page": emails[:30], "text": text[:8000]}
