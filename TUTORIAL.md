# 📘 Tutorial — Building a Networking Contacts App with AI Search

> A complete beginner-friendly guide to building and deploying an AI-powered contact book using Python, Streamlit, Supabase, and OpenAI.

---

## 🌟 Support & Connect

Before we start — if you find this tutorial helpful, it would mean a lot:

| | |
|---|---|
| ⭐ **Star the repo** | [github.com/adityasharmadotai-hash](https://github.com/adityasharmadotai-hash) |
| 💼 **Follow on LinkedIn** | [linkedin.com/in/aditya-hicounselor](https://www.linkedin.com/in/aditya-hicounselor/) |
| 📺 **Subscribe on YouTube** | [YouTube Channel](https://www.youtube.com/channel/UCPjQtVNUrf7EKrm8ZoqrCAQ) |
| 🚀 **AI Jobs in the USA** | [Join the Waitlist](https://docs.google.com/forms/d/e/1FAIpQLSc3gJssBV3B25EZ3sYA7Qcen9NbtOB_wgQaturfB7lTXuAdLQ/viewform) |

---

## 📋 Table of Contents

1. [What We Are Building and Why](#1-what-we-are-building-and-why)
2. [How It Works](#2-how-it-works)
3. [Prerequisites Checklist](#3-prerequisites-checklist)
4. [Project Setup](#4-project-setup)
5. [Setting Up Supabase](#5-setting-up-supabase)
6. [The Full App Code — Explained](#6-the-full-app-code--explained)
   - [Imports and Page Config](#61-imports-and-page-config)
   - [Custom Styling](#62-custom-styling)
   - [Hero Section](#63-hero-section)
   - [Supabase Connection](#64-supabase-connection)
   - [AI Query Function](#65-ai-query-function)
   - [Tab 1: Add Contact](#66-tab-1-add-contact)
   - [Tab 2: View All Contacts](#67-tab-2-view-all-contacts)
   - [Tab 3: Ask AI](#68-tab-3-ask-ai)
7. [How to Run Locally](#7-how-to-run-locally)
8. [How to Deploy on Streamlit Cloud](#8-how-to-deploy-on-streamlit-cloud)
9. [Common Errors and Fixes](#9-common-errors-and-fixes)
10. [What You Learned](#10-what-you-learned)
11. [What's Next](#11-whats-next)

---

## 1. What We Are Building and Why

### The Problem

You go to a networking event. You meet 15 people in 3 hours. You get their cards, save numbers, maybe connect on LinkedIn. Then two weeks later you have zero memory of who was who, what they worked on, or where you met them.

### The Solution

A personal contact book you can open on your phone the second you meet someone. You type their name, email, and a quick note like *"Met at AI Summit 2025, works at Google, wants to chat about LLMs"* — and it's saved instantly to a database.

Later, you can ask the AI:
- *"Who did I meet at an AI conference?"*
- *"Show me everyone who works in product management"*
- *"Find people I should follow up with from New York"*

### Why This Stack?

| Tool | Why We Use It |
|------|--------------|
| **Streamlit** | Build a web app in pure Python — no HTML, CSS, or JavaScript knowledge needed |
| **Supabase** | Free cloud database that takes 5 minutes to set up — no server, no DevOps |
| **OpenAI** | Powers the natural language AI search feature |
| **Streamlit Cloud** | Free hosting — one click and you get a public URL |

This entire app is **one Python file** and about **150 lines of code**. That's it.

---

## 2. How It Works

```
┌─────────────────────────────────────────────────────────┐
│                   USER ON PHONE/BROWSER                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   STREAMLIT APP (app.py)                │
│                                                         │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────┐   │
│   │  ➕ Add      │  │  📋 View All  │  │  🤖 Ask AI  │   │
│   │  Contact    │  │  Contacts    │  │             │   │
│   └──────┬──────┘  └──────┬───────┘  └──────┬──────┘   │
└──────────┼────────────────┼─────────────────┼──────────┘
           │                │                 │
           ▼                ▼                 ▼
┌──────────────────┐  ┌──────────────┐  ┌────────────────┐
│  SUPABASE DB     │  │  SUPABASE DB │  │  OPENAI GPT-4o │
│  INSERT new row  │  │  SELECT rows │  │  Read contacts │
│                  │  │              │  │  Answer query  │
└──────────────────┘  └──────────────┘  └────────────────┘
```

**Step by step:**
1. You open the app URL on your phone
2. You type a contact's details and hit **Save** → the app sends the data to Supabase
3. Supabase stores it in a table called `contacts`
4. When you click **All Contacts**, the app fetches all rows from Supabase and shows them
5. When you **Ask AI**, the app fetches all contacts, passes them to OpenAI along with your question, and GPT-4o returns a smart answer

---

## 3. Prerequisites Checklist

Before starting, make sure you have:

- [ ] **Python 3.9+** installed on your computer ([download here](https://python.org))
- [ ] A **free Supabase account** — [supabase.com](https://supabase.com)
- [ ] An **OpenAI API key** — [platform.openai.com](https://platform.openai.com)
- [ ] A **GitHub account** — [github.com](https://github.com)
- [ ] A **Streamlit Cloud account** — [share.streamlit.io](https://share.streamlit.io) (sign in with GitHub)
- [ ] Basic comfort with Python (variables, functions, if/else)

You do **not** need to know:
- HTML or CSS
- Databases or SQL beyond copy-pasting the setup command
- JavaScript or any frontend framework
- Cloud infrastructure or DevOps

---

## 4. Project Setup

### Create your project folder

```bash
mkdir networking-app
cd networking-app
```

### Create the files

```bash
touch app.py
touch requirements.txt
touch .gitignore
```

### Fill in requirements.txt

Open `requirements.txt` and paste:

```
streamlit>=1.35.0
supabase>=2.4.0
openai>=1.30.0
pandas>=2.0.0
```

These are the four Python libraries the app needs:
- `streamlit` — builds the web interface
- `supabase` — talks to your Supabase database
- `openai` — talks to OpenAI's GPT-4o
- `pandas` — handles the table of contacts

### Fill in .gitignore

```
__pycache__/
*.pyc
.env
.streamlit/secrets.toml
```

This tells Git to never upload your secret API keys to GitHub.

### Install the libraries

```bash
pip install -r requirements.txt
```

---

## 5. Setting Up Supabase

### Create a project

1. Go to [supabase.com](https://supabase.com) and sign up for free
2. Click **New Project**
3. Give it a name (e.g. `networking-app`) and set a database password
4. Choose any region close to you
5. Wait about 60 seconds for it to provision

### Create the contacts table

1. In the left sidebar, click **SQL Editor**
2. Paste this and click **Run**:

```sql
create table contacts (
  id bigint generated always as identity primary key,
  name text,
  email text,
  phone text,
  linkedin text,
  notes text,
  created_at timestamp with time zone default now()
);

alter table contacts disable row level security;
```

**What this does:**
- Creates a table called `contacts` with 7 columns
- `id` is a unique number that auto-increments for each row
- `created_at` automatically records when each contact was added
- `disable row level security` lets the app read and write without authentication

### Get your API credentials

1. Go to **Project Settings** (gear icon) → **API**
2. Copy the **Project URL** — this is your `SUPABASE_URL`
3. Click **Copy** next to **Publishable key** — this is your `SUPABASE_KEY`

---

## 6. The Full App Code — Explained

Open `app.py`. The full code is below, broken into sections with explanations.

---

### 6.1 Imports and Page Config

```python
import streamlit as st
from supabase import create_client
from openai import OpenAI
import pandas as pd
```

**What each import does:**
- `streamlit` — every `st.` command you see builds something in the UI
- `create_client` — the function we use to connect to Supabase
- `OpenAI` — the class we use to send questions to GPT-4o
- `pandas` — lets us work with the contacts data as a table (DataFrame)

```python
st.set_page_config(
    page_title="Never Lose a Contact",
    page_icon="🤝",
    layout="centered"
)
```

This sets the browser tab title, the favicon emoji, and keeps the layout centered (better on mobile).

---

### 6.2 Custom Styling

```python
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
...
</style>
""", unsafe_allow_html=True)
```

**Plain English:** Streamlit lets you inject raw CSS to change how the app looks. Here we:
- Import a nicer font (Inter) from Google Fonts
- Define the purple gradient hero card
- Style the stat cards, tab buttons, form sections, and AI answer box

`unsafe_allow_html=True` is required whenever you pass raw HTML or CSS to Streamlit.

---

### 6.3 Hero Section

```python
st.markdown("""
<div class="hero">
    <div style="font-size:2.4rem">🤝</div>
    <h1>Save Contacts,<br>Never Lose a Connection</h1>
    <p>Capture people you meet at events — instantly searchable with AI</p>
    <div class="badge-row">
        <span class="badge">📇 Smart Contact Book</span>
        <span class="badge">☁️ Saved to Supabase</span>
        <span class="badge">🤖 AI-Powered Search</span>
    </div>
</div>
""", unsafe_allow_html=True)
```

This renders the purple gradient banner at the top of the page. It's pure HTML that uses the CSS classes we defined above.

---

### 6.4 Supabase Connection

```python
@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
```

**Plain English:**
- `st.secrets` reads your API keys from Streamlit's secrets manager (so they're never in the code)
- `create_client()` opens a connection to your Supabase database
- `@st.cache_resource` means Streamlit only creates this connection once, then reuses it — faster and more efficient

```python
def load_contacts() -> pd.DataFrame:
    response = get_client().table("contacts").select("name, email, phone, linkedin, notes").order("id").execute()
    if not response.data:
        return pd.DataFrame(columns=["Name", "Email", "Phone", "LinkedIn", "Notes"])
    return pd.DataFrame(response.data).rename(columns={
        "name": "Name", "email": "Email", "phone": "Phone",
        "linkedin": "LinkedIn", "notes": "Notes",
    })
```

**Plain English:**
- `.table("contacts")` — points to our contacts table in Supabase
- `.select(...)` — picks which columns to fetch (like `SELECT` in SQL)
- `.order("id")` — returns rows in the order they were added
- `.execute()` — actually runs the query and returns results
- We then convert the result into a pandas DataFrame (a table) and rename the columns to have capital letters for display

```python
def save_contact(name, email, phone, linkedin, notes):
    get_client().table("contacts").insert({
        "name": name, "email": email, "phone": phone,
        "linkedin": linkedin, "notes": notes,
    }).execute()
```

**Plain English:** This sends a new row to Supabase. The dictionary `{"name": name, ...}` maps column names to the values we want to insert. It's the Python equivalent of `INSERT INTO contacts ...` in SQL.

---

### 6.5 AI Query Function

```python
def ask_ai(question: str, df: pd.DataFrame) -> str:
    if df.empty:
        return "You don't have any contacts saved yet. Add some first!"

    contacts_text = df.to_json(orient="records", indent=2)

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that searches through the user's networking contacts. "
                    "When the user asks a question, look through the contact data and return the relevant people "
                    "with their details formatted clearly. Be concise and friendly."
                ),
            },
            {
                "role": "user",
                "content": f"Here are my contacts:\n\n{contacts_text}\n\nMy question: {question}",
            },
        ],
    )
    return response.choices[0].message.content
```

**Plain English — this is the AI magic:**

1. `df.to_json(orient="records")` — converts your contact table into a JSON string (a format GPT-4o can read easily)
2. We send two messages to GPT-4o:
   - A **system message** that tells GPT who it is and what job to do
   - A **user message** that contains ALL your contacts as data, plus your question
3. GPT-4o reads through all the contacts and writes a natural language answer
4. We return that answer and display it in the app

This is a simple form of **RAG (Retrieval-Augmented Generation)** — we're giving the AI real data (your contacts) to reason over rather than relying on its training data.

---

### 6.6 Tab 1: Add Contact

```python
tab_add, tab_view, tab_ai = st.tabs(["➕  Add Contact", "📋  All Contacts", "🤖  Ask AI"])

with tab_add:
    with st.form("add_contact_form", clear_on_submit=True):
        name  = st.text_input("Full Name *", placeholder="e.g. Sarah Chen")
        email = st.text_input("Email Address", placeholder="sarah@example.com")
        ...
        submitted = st.form_submit_button("💾  Save Contact", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("Name is required.")
        else:
            save_contact(name.strip(), email.strip(), ...)
            st.success(f"✅ {name} saved!")
```

**Plain English:**
- `st.tabs(...)` creates the three clickable tabs at the top
- `st.form(...)` groups all the inputs together so nothing is sent until the button is clicked
- `clear_on_submit=True` clears the form after saving — ready for the next contact
- `name.strip()` removes any accidental spaces the user might have typed
- `st.error()` and `st.success()` show red and green message banners

---

### 6.7 Tab 2: View All Contacts

```python
with tab_view:
    df = load_contacts()
    
    # Show stat cards
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card">
            <div class="icon">👥</div>
            <div>{len(df)}</div>
            <div class="label">Total Contacts</div>
        </div>
        ...
    </div>
    """, unsafe_allow_html=True)

    # Search filter
    search = st.text_input("🔍  Search contacts", placeholder="Filter by any field…")
    if search:
        mask = df.apply(
            lambda row: row.astype(str).str.contains(search, case=False).any(),
            axis=1,
        )
        df = df[mask]

    st.dataframe(df, use_container_width=True, hide_index=True)
```

**Plain English:**
- We load all contacts from Supabase first
- `len(df)` counts total rows, `df['Email'].astype(bool).sum()` counts non-empty emails
- The search filter works by checking if the search term appears in **any column** of each row — that's what the `lambda` function does
- `st.dataframe()` renders the contacts as a nice interactive table

---

### 6.8 Tab 3: Ask AI

```python
with tab_ai:
    question = st.text_input("Your question", placeholder="Ask in plain English…")
    if st.button("✨  Ask AI", type="primary", use_container_width=True):
        with st.spinner("Searching your contacts…"):
            df = load_contacts()
            answer = ask_ai(question.strip(), df)
            st.markdown(
                f'<div class="ai-answer">{answer}</div>',
                unsafe_allow_html=True,
            )
```

**Plain English:**
- `st.spinner(...)` shows an animated loading message while we wait for OpenAI to respond
- We fetch all contacts fresh each time (so new contacts are always included)
- The answer is wrapped in a styled HTML div so it looks distinct from the rest of the page

---

## 7. How to Run Locally

### Step 1 — Add your secrets

Create a file called `.streamlit/secrets.toml` (note: this file is in your `.gitignore` so it won't be pushed to GitHub):

```bash
mkdir .streamlit
touch .streamlit/secrets.toml
```

Open it and paste:

```toml
OPENAI_API_KEY = "sk-..."
SUPABASE_URL   = "https://xxxx.supabase.co"
SUPABASE_KEY   = "sb_publishable_..."
```

### Step 2 — Run the app

```bash
streamlit run app.py
```

Your browser will open to `http://localhost:8501`. Try adding a contact and check that it appears in your Supabase table (you can see it under **Table Editor** in the Supabase dashboard).

---

## 8. How to Deploy on Streamlit Cloud

### Step 1 — Push to GitHub

```bash
git init
git add app.py requirements.txt .gitignore README.md TUTORIAL.md
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/networking-app.git
git push -u origin main
```

### Step 2 — Create the app on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app**
3. Choose your GitHub repo and select `app.py` as the main file
4. Click **Advanced settings**
5. Under **Secrets**, paste your three keys:

```toml
OPENAI_API_KEY = "sk-..."
SUPABASE_URL   = "https://xxxx.supabase.co"
SUPABASE_KEY   = "sb_publishable_..."
```

6. Click **Deploy**

Within about 60 seconds, Streamlit will give you a public URL like:
`https://yourname-networking-app.streamlit.app`

Open it on your phone — bookmark it — and you're done.

> **Tip:** Any time you push a new commit to GitHub, Streamlit Cloud automatically redeploys. You never need to manually redeploy.

---

## 9. Common Errors and Fixes

| Error | What it means | Fix |
|-------|--------------|-----|
| `st.secrets has no key "SUPABASE_URL"` | Secrets not added to Streamlit Cloud | Go to app settings → Secrets and add your keys |
| `new row violates row-level security policy` | RLS is enabled on the contacts table | Run `alter table contacts disable row level security;` in Supabase SQL Editor |
| `relation "contacts" already exists` | You already ran the CREATE TABLE command | Just run the `alter table` line on its own |
| `SyntaxError: invalid syntax` | Smart/curly quotes in the code | Make sure all quotes in code are straight `"` not `"` `"` |
| `Could not load contacts: 'LinkedIn'` | Column name mismatch | Make sure the rename dictionary in `load_contacts()` uses `"linkedin": "LinkedIn"` |
| `ModuleNotFoundError: No module named 'supabase'` | Library not installed | Run `pip install -r requirements.txt` |
| App loads but AI gives wrong answers | GPT hallucinating | Try rephrasing your question — be more specific about names or event details |

---

## 10. What You Learned

By building this project, you now know how to:

- ✅ **Build a real web app in Python** using Streamlit — no HTML or JavaScript required
- ✅ **Connect to a cloud database** using Supabase — insert and query data with just a few lines
- ✅ **Use the OpenAI API** to add AI-powered natural language search to any app
- ✅ **Handle secrets safely** — never hardcoding API keys in your code
- ✅ **Deploy an app for free** and share it as a public URL anyone can open on their phone
- ✅ **Apply RAG (Retrieval-Augmented Generation)** in its simplest form — give an AI model real data and ask it questions

---

## 11. What's Next

Here are some ideas to extend this project:

### Easier improvements
- **Export to CSV** — add a download button so you can export all contacts
- **Delete a contact** — add a delete button next to each row
- **Edit a contact** — click a row to update the details

### Intermediate improvements
- **Tags/categories** — add a "where I met them" tag like Conference, Online, Intro
- **Follow-up reminders** — add a "follow up by" date field and highlight overdue contacts
- **Contact photo** — let users paste a LinkedIn photo URL

### Advanced improvements
- **Email integration** — one-click to draft a follow-up email via Gmail API
- **LinkedIn scraping** — auto-fill details by pasting a LinkedIn URL
- **Voice input** — use OpenAI Whisper to speak contact details instead of typing
- **Semantic search** — use embeddings instead of passing all contacts to GPT (better for large contact lists)

---

## 🙏 Thank You

If you made it this far — you built something real. An AI-powered app, deployed to the cloud, accessible from any phone in the world.

That's not a tutorial project. That's a tool you'll actually use.

If this helped you, please:

| | |
|---|---|
| ⭐ **Star the repo** | [github.com/adityasharmadotai-hash](https://github.com/adityasharmadotai-hash) |
| 💼 **Follow on LinkedIn** | [linkedin.com/in/aditya-hicounselor](https://www.linkedin.com/in/aditya-hicounselor/) |
| 📺 **Subscribe on YouTube** | [YouTube Channel](https://www.youtube.com/channel/UCPjQtVNUrf7EKrm8ZoqrCAQ) |
| 🚀 **AI Jobs in the USA** | [Join the Waitlist](https://docs.google.com/forms/d/e/1FAIpQLSc3gJssBV3B25EZ3sYA7Qcen9NbtOB_wgQaturfB7lTXuAdLQ/viewform) |

Also check out the companion project:
👉 **[Docs Reader RAG Agent](https://github.com/adityasharmadotai-hash/docs-reader-rag-agent/blob/main/TUTORIAL.md)** — build an AI that reads your documents and answers questions about them

---

*Built with ❤️ by Aditya Sharma*
