"""Connect a Gmail account (run once per account you want to send from).

1. Google Cloud Console > APIs & Services: enable the Gmail API.
2. OAuth consent screen: for Google Workspace (e.g. @yourcompany.com) choose
   "Internal" so everyone in your domain can sign in without app verification.
3. Credentials > Create OAuth client ID > "Desktop app". Download the JSON
   and save it as chief-of-staff/gmail_credentials.json
4. From chief-of-staff/ run:   python scripts/gmail_auth.py
   A browser opens: pick the account to connect. Repeat for each account.

Tokens are saved to gmail_tokens/<email>.json.
"""
import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_secrets_file(os.path.join(ROOT, "gmail_credentials.json"), SCOPES)
    # prompt=select_account forces Google's account chooser so you can pick a different account each run
    creds = flow.run_local_server(port=0, prompt="select_account consent")
    email = build("gmail", "v1", credentials=creds, cache_discovery=False) \
        .users().getProfile(userId="me").execute()["emailAddress"].lower()
    os.makedirs(os.path.join(ROOT, "gmail_tokens"), exist_ok=True)
    path = os.path.join(ROOT, "gmail_tokens", f"{email}.json")
    with open(path, "w") as f:
        f.write(creds.to_json())
    connected = sorted(p[:-5] for p in os.listdir(os.path.join(ROOT, "gmail_tokens")) if p.endswith(".json"))
    print(f"\nConnected {email}.")
    print("All connected accounts:", ", ".join(connected))
    print("Run this script again to add another account. Restart app.py to pick up changes.")
