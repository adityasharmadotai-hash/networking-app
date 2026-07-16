import os
import pickle
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",   # needed to detect replies
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
CREDENTIALS_FILE = "gmail_credentials.json"
TOKEN_FILE = "gmail_token.json"

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

# Write URL to file so it doesn't get truncated in terminal
with open("auth_url.txt", "w") as f:
    f.write(auth_url)

print("\n" + "="*60)
print("STEP 1: Open this file in Finder and copy the full URL inside:")
print("   outreach-agent/auth_url.txt")
print("\nOR run this to open it directly:")
print("   open auth_url.txt")
print("="*60)
print("\nSTEP 2: Paste that URL into your browser")
print("STEP 3: Sign in as susan@hiregen.co and click Allow")
print("STEP 4: Google will show you a code — copy it")
print("STEP 5: Paste the code below and press Enter\n")

code = input("Enter the authorization code: ").strip()

flow.fetch_token(code=code)
creds = flow.credentials

with open(TOKEN_FILE, "wb") as f:
    pickle.dump(creds, f)

print(f"\nSuccess! gmail_token.json created.")
print("Gmail + Sheets access connected.")
