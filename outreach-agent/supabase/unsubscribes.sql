-- Permanent suppression list: emails that must never be contacted again.
-- Survives lead resets, so an unsubscribe is honored across all future campaigns.
create table if not exists unsubscribes (
    email      text primary key,
    reason     text,                       -- reply | manual | bounce
    created_at timestamptz default now()
);

create index if not exists idx_unsubscribes_email on unsubscribes(email);
