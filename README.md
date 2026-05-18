# Networking Contacts App

A simple Streamlit app to save and search networking contacts, backed by Google Sheets and Claude AI.

---

## One-time setup (takes ~15 minutes)

### Step 1 — Get your OpenAI API key

1. Go to [platform.openai.com](https://platform.openai.com) and sign up / log in.
2. Click **API Keys → Create new secret key**. Copy the key (starts with `sk-`).

---

### Step 2 — Create a Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new blank sheet.
2. Name it exactly: **Networking Contacts** (or any name you like — you'll use it in Step 4).
3. Leave it empty — the app will add the header row automatically.

---

### Step 3 — Create a Google Cloud service account

This lets the app write to your sheet without a login popup.

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Create a new project (or use an existing one).
3. In the search bar type **"Google Sheets API"** → Enable it.
4. In the search bar type **"Google Drive API"** → Enable it.
5. Go to **IAM & Admin → Service Accounts → Create Service Account**.
   - Name: `networking-app` (anything works)
   - Click **Done** (skip optional steps).
6. Click the service account you just created → **Keys tab → Add Key → Create new key → JSON**.
7. A `.json` file downloads. Open it — you'll copy values from it in Step 4.

---

### Step 4 — Share your Google Sheet with the service account

1. Open the `.json` file you downloaded. Find the `"client_email"` value — it looks like  
   `networking-app@your-project.iam.gserviceaccount.com`
2. Open your Google Sheet → **Share** → paste that email → set role to **Editor** → Send.

---

### Step 5 — Install and run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Test it — add a contact and make sure it appears in your Google Sheet.

---

## Deploy to Streamlit Community Cloud (free, public URL)

1. Push this repo to GitHub (the `.gitignore` already excludes `secrets.toml`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → pick your repo → `app.py`.
3. Click **Advanced settings → Secrets** and paste the entire contents of your `secrets.toml` there.
4. Click **Deploy**. You get a public URL like `https://yourname-networking-app.streamlit.app` — open it on your phone!

---

## How to use

| Tab | What it does |
|-----|-------------|
| ➕ Add Contact | Fill in name, email, phone, LinkedIn, notes → Save |
| 📋 All Contacts | See everyone; filter by typing in the search box |
| 🤖 Ask AI | Type a question in plain English — "Who did I meet at an AI conference?" |
