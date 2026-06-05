CREATE TABLE IF NOT EXISTS email_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_data JSONB NOT NULL,
    email_type TEXT NOT NULL DEFAULT 'intro',
    scheduled_for TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | failed
    sent_at TIMESTAMPTZ,
    gmail_message_id TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON email_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_scheduled ON email_queue(scheduled_for);
