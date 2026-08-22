-- Wizard session persistence
-- Run once against your Supabase project (SQL editor).
--
-- Streamlit clears st.session_state whenever the browser reconnects with a new
-- session id (refresh, laptop sleep, idle websocket timeout, container recycle).
-- Parking the wizard state here means an idle tab no longer loses the whole
-- discovery run - the app reloads it from the `sid` in the URL.

create table if not exists wizard_sessions (
    id         text primary key,          -- opaque session id, kept in the URL
    state      jsonb not null,            -- serialized wizard state
    updated_at timestamptz default now()
);

create index if not exists idx_wizard_sessions_updated on wizard_sessions(updated_at);
