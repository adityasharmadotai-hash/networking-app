# Chief of Staff: Chess + team

A personal command center powered by **Gemini**.

- **Chess (Chief of Staff)**: your main agent. Plans your requests, hands work to the team, and reports back.
- **Alex (Deep Research & Outreach)**: researches companies, talent and people; finds contact details and email addresses; updates HubSpot; sends email from your Gmail.

You can talk to Chess, or click any agent on the left and talk to it directly. When Chess delegates, the request shows up in that agent's thread ("Chess asked Alex") so you can follow along or step in.

Emails are never sent silently. Each one appears as a draft card in the chat with **Send** / **Discard** (you can edit it first), unless you set `AUTO_SEND_EMAIL=true`.

## Setup

```bash
cd chief-of-staff
pip install -r requirements.txt
cp .env.example .env        # then fill it in (see below)
python app.py               # open http://localhost:8000
```

| Setting | What it unlocks | Where to get it |
|---|---|---|
| `GEMINI_API_KEY` | **Required.** All agents run on Gemini | https://aistudio.google.com/apikey |
| `GEMINI_MODEL` | Model choice (default `gemini-2.5-flash`; set `CHESS_MODEL` / `ALEX_MODEL` to override per agent) | |
| `ALEX_GMAIL_ACCOUNT` | The one Gmail account Alex sends from (each agent gets its own mailbox) | Then connect it once, see **Connecting Gmail** below |
| `HUBSPOT_ACCESS_TOKEN` | Create/update contacts, companies and notes | HubSpot → Settings → Integrations → Private Apps (scopes: `crm.objects.contacts.read/write`, `crm.objects.companies.read/write`) |
| `HUNTER_API_KEY` | Verified email finding and company email directories | https://hunter.io/api-keys. Without it, Alex uses public pages plus pattern guesses, clearly labelled as unverified |
| `SENDER_NAME`, `USER_TITLE`, `EMAIL_SIGNATURE` | Your name in the dashboard and the signature on every email | |
| `APP_PASSWORD` | Password-protects the dashboard if you deploy it | |

## Connecting Gmail

Each agent sends from exactly one Gmail account, set in `.env` (for example `ALEX_GMAIL_ACCOUNT`). An agent can never send from another agent's mailbox. To connect an account:

1. In [Google Cloud Console](https://console.cloud.google.com/) create a project (or reuse one) and enable the **Gmail API**.
2. **OAuth consent screen**: for a Google Workspace domain choose **Internal**, so accounts in your domain can sign in without Google's app review.
3. **Credentials → Create credentials → OAuth client ID → Desktop app**. Download the JSON and save it as `chief-of-staff/gmail_credentials.json`.
4. Run `python scripts/gmail_auth.py`. In the browser, pick the account you assigned (for Alex, the `ALEX_GMAIL_ACCOUNT` address).

The token is saved in `gmail_tokens/` (git-ignored). When you add an agent with its own mailbox later, run the script again and sign in as that account.

## What Alex can do (tools)

`web_research` (Gemini + Google Search grounding, with sources) · `fetch_url` (reads team/contact pages and extracts emails) · `find_email` · `verify_email` · `company_email_directory` · `hubspot_upsert_contact` · `hubspot_upsert_company` · `hubspot_search_contacts` · `send_email` · `create_gmail_draft`

Chess has `delegate_to_agent`, `list_team`, `web_research` and `fetch_url`.

## Adding another agent

Add an entry to `AGENTS` in `core/agents.py` (name, title, color, prompt, list of tools, and optionally a `gmail_account`). It shows up in the sidebar automatically, and Chess learns about it from the team roster. New tools go in `core/toolbox.py`.

## Layout

```
app.py              FastAPI server + API
core/agents.py      agent definitions (Chess, Alex) and prompts
core/runner.py      Gemini function-calling loop
core/toolbox.py     tool schemas + dispatch (incl. delegation)
core/store.py       SQLite: threads, activity, email approvals
tools/              research, email finding, HubSpot, Gmail
static/index.html   dashboard
```
