"""
One-time helper: generate GMAIL_TOKEN_B64 for Render / Streamlit deployment.

Prerequisite:
  - gmail_credentials.json (an OAuth *Desktop app* client, downloaded from the
    Google Cloud Console) placed in this same folder (outreach-agent/).

Run it LOCALLY (it opens a browser — cannot run on Render):
    cd outreach-agent
    pip install -r requirements.txt
    python generate_gmail_token.py

Sign in with the account you send FROM (must match SENDER_EMAIL). It saves
gmail_token.json and prints the GMAIL_TOKEN_B64 value to paste into your
Render service's environment variables.
"""
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",   # needed to detect replies
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_secrets_file("gmail_credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)  # opens a browser for consent

    # Save a local copy as portable JSON (works across google-auth versions;
    # a pickle would break on hosts pinned to an older google-auth, e.g. Render).
    token_json = creds.to_json()
    with open("gmail_token.json", "w") as f:
        f.write(token_json)

    # ...and print the base64 form for the GMAIL_TOKEN_B64 env var.
    token_b64 = base64.b64encode(token_json.encode()).decode()
    print("\n" + "=" * 72)
    print("GMAIL_TOKEN_B64  (copy the entire single line below):\n")
    print(token_b64)
    print("=" * 72)
    print("\nSet this as GMAIL_TOKEN_B64 on your Render dashboard AND worker services,")
    print("then set SENDER_EMAIL to the account you just signed in as.")
