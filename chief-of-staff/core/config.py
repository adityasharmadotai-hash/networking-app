import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


def env(key, default=""):
    return os.getenv(key, default).strip()


GEMINI_API_KEY = env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")
CHESS_MODEL = env("CHESS_MODEL") or GEMINI_MODEL
ALEX_MODEL = env("ALEX_MODEL") or GEMINI_MODEL
RESEARCH_MODEL = env("RESEARCH_MODEL") or GEMINI_MODEL

HUBSPOT_ACCESS_TOKEN = env("HUBSPOT_ACCESS_TOKEN")
HUNTER_API_KEY = env("HUNTER_API_KEY")

SENDER_EMAIL = env("SENDER_EMAIL")
SENDER_NAME = env("SENDER_NAME")
USER_TITLE = env("USER_TITLE")            # e.g. "CEO, Acme"
# Appended to every email the agents write. Use \n for line breaks in .env.
EMAIL_SIGNATURE = env("EMAIL_SIGNATURE").replace("\\n", "\n")
# Emails are queued for your approval in the dashboard unless this is "true".
AUTO_SEND_EMAIL = env("AUTO_SEND_EMAIL", "false").lower() == "true"

# Optional password for the dashboard (HTTP basic auth, any username).
APP_PASSWORD = env("APP_PASSWORD")

MAX_TOOL_STEPS = int(env("MAX_TOOL_STEPS", "15"))
