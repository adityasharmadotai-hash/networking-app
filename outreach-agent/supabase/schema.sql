-- Leads discovered from job boards
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL,
    job_title_hiring_for TEXT,
    job_url TEXT,
    job_source TEXT,                        -- indeed, linkedin, google_jobs, etc.
    contact_name TEXT,
    contact_title TEXT,
    contact_linkedin_url TEXT,
    contact_email TEXT,
    status TEXT DEFAULT 'new',              -- new | emailed | following_up | replied | closed | skipped
    followup_count INTEGER DEFAULT 0,
    next_followup_date DATE,
    last_contacted_at TIMESTAMPTZ,
    gmail_thread_id TEXT,                    -- Gmail thread id of the intro (follow-ups reply into it)
    rfc_message_id TEXT,                     -- RFC822 Message-ID of the intro (used as In-Reply-To)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Every email sent (intro + follow-ups)
CREATE TABLE IF NOT EXISTS emails_sent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    email_type TEXT NOT NULL,               -- intro | followup_1 | followup_2 | followup_3 | followup_4 | followup_5
    to_email TEXT NOT NULL,
    to_name TEXT,
    subject TEXT,
    body TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    gmail_message_id TEXT,
    gmail_thread_id TEXT,                    -- thread this message landed in
    rfc_message_id TEXT                      -- this message's own Message-ID header
);

-- Activity log for dashboard
CREATE TABLE IF NOT EXISTS activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,              -- lead_found | email_sent | followup_sent | reply_received | lead_skipped
    description TEXT,
    lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_next_followup ON leads(next_followup_date);
CREATE INDEX IF NOT EXISTS idx_emails_lead_id ON emails_sent(lead_id);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC);

-- Auto-update updated_at on leads
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
