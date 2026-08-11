-- Follow-up threading support
-- Run this once against your Supabase project (SQL editor) before deploying the
-- threading change. Stores the Gmail thread id + RFC Message-ID of each intro so
-- follow-ups can reply into the same conversation instead of starting a new thread.

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS gmail_thread_id TEXT,   -- Gmail internal thread id of the intro
    ADD COLUMN IF NOT EXISTS rfc_message_id  TEXT;   -- RFC822 Message-ID header of the intro

ALTER TABLE emails_sent
    ADD COLUMN IF NOT EXISTS gmail_thread_id TEXT,   -- thread this message landed in
    ADD COLUMN IF NOT EXISTS rfc_message_id  TEXT;   -- this message's own Message-ID header
