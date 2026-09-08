-- Campaign grouping + reply tracking
-- Run once against your Supabase project (SQL editor), after schema.sql and
-- email_queue.sql.
--
-- These columns are written by the dashboard (campaign_id / campaign_name),
-- the scheduler (emails_sent.campaign_id) and the reply checker
-- (leads.response_status / response_snippet), but they were never added to the
-- committed schema. Without them the History tab cannot group a run into a
-- named campaign and falls back to grouping by send date.
--
-- Every statement is idempotent, so it is safe to re-run.

-- Which outreach run an email belongs to.
ALTER TABLE email_queue ADD COLUMN IF NOT EXISTS campaign_id   TEXT;
ALTER TABLE email_queue ADD COLUMN IF NOT EXISTS campaign_name TEXT;

-- emails_sent stores the id only; the human-readable name lives on the queue
-- rows, which is where the History tab reads it from.
ALTER TABLE emails_sent ADD COLUMN IF NOT EXISTS campaign_id TEXT;

-- Reply / bounce classification written by agent/reply_checker.py.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS response_status  TEXT;  -- positive | negative | bounced | unsubscribed | other
ALTER TABLE leads ADD COLUMN IF NOT EXISTS response_snippet TEXT;

CREATE INDEX IF NOT EXISTS idx_queue_campaign  ON email_queue(campaign_id);
CREATE INDEX IF NOT EXISTS idx_emails_campaign ON emails_sent(campaign_id);
CREATE INDEX IF NOT EXISTS idx_leads_response  ON leads(response_status);
