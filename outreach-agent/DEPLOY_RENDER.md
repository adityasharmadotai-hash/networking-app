# Deploying the Outreach Agent on Render

The Streamlit **dashboard** only *queues* emails into the `email_queue` table. The
**scheduler** (`scheduler.py`) is the always-on process that actually *sends* them.
Render runs that scheduler as a background worker.

## Architecture

```
Streamlit dashboard  ──inserts pending rows──►  Supabase `email_queue`
(Streamlit Cloud or Render web)                        │
                                                        ▼
                              Render Worker (scheduler.py, 24/7)
                              • every 30s: send due emails (8am–6pm PT)
                              • every 3 days: queue follow-ups
                              • every 4h: check Gmail for replies
```

## Steps

1. **Push to GitHub** (this branch or `main`).
2. In Render: **New + → Blueprint**, select this repo. Render reads
   [`render.yaml`](render.yaml) and creates the `hiregen-scheduler` worker.
3. Set the secret env vars (marked `sync: false` in the blueprint):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `GMAIL_TOKEN_B64` — base64 of your `gmail_token.json`
4. Click **Apply / Deploy**. The worker starts and restarts automatically on failure.

### Generating `GMAIL_TOKEN_B64`

The scheduler authenticates to Gmail with the same OAuth token pickle used locally.
Encode it to a single base64 line and paste it as the env var value:

```bash
# macOS / Linux
base64 -w0 gmail_token.json

# Windows (PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("gmail_token.json"))
```

## Verifying it works

- Render → your worker → **Logs**: you should see the `HireGen Email Scheduler`
  banner and periodic `Outside send window` / `email(s) sent` lines.
- Dashboard → **History → Emails Pending in Queue**: rows should move from
  *pending* to delivered during the 8am–6pm PT window.

## Notes

- Render background workers require a **paid** instance type (Free tier does not
  keep workers running). `starter` is the smallest option.
- The worker only needs Supabase + Gmail credentials — it does **not** discover
  jobs or find contacts, so `SERPAPI_KEY` / `WIZA_API_KEY` are not required here.
- To also host the dashboard on Render, uncomment the `web` service block in
  `render.yaml` and add its extra secrets.
