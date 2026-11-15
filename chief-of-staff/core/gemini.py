"""Shared Gemini client."""
from google import genai

from . import config

_client = None


def client():
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to chief-of-staff/.env and restart.")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client
