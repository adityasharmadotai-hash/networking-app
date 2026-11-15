"""One-time Gmail connection.

1. Google Cloud Console > APIs & Services: enable the Gmail API.
2. Credentials > Create OAuth client ID > "Desktop app". Download the JSON
   and save it as chief-of-staff/gmail_credentials.json
3. Run (from chief-of-staff/):  python scripts/gmail_auth.py
   Sign in with the Gmail account you want the agents to send from.

Creates gmail_token.json and prints GMAIL_TOKEN_B64 for cloud deploys.
"""
import base64
import os

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_secrets_file(os.path.join(ROOT, "gmail_credentials.json"), SCOPES)
    creds = flow.run_local_server(port=0)
    token = creds.to_json()
    with open(os.path.join(ROOT, "gmail_token.json"), "w") as f:
        f.write(token)
    print("Saved gmail_token.json. Gmail is connected.\n")
    print("For cloud deploys, set GMAIL_TOKEN_B64 to:\n")
    print(base64.b64encode(token.encode()).decode())
