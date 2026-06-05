import os
import sys
import uuid
import random
import pickle
import pandas as pd
import streamlit as st
from datetime import date, timedelta, datetime, timezone
from zoneinfo import ZoneInfo
PACIFIC = ZoneInfo("America/Los_Angeles")
from dotenv import load_dotenv
from supabase import create_client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.job_discovery import discover_jobs, ALL_ROLES, ALL_LOCATIONS
from agent.dedup import get_existing_clients, get_already_contacted, normalize
from agent.email_sender import send_email, render_template, EMAIL_TEMPLATES
from streamlit_quill import st_quill

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Load from Streamlit secrets (cloud) with .env fallback (local)
def _secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)

SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = _secret("SUPABASE_SERVICE_ROLE_KEY")
DAILY_EMAIL_LIMIT = int(_secret("DAILY_EMAIL_LIMIT", "20"))
FOLLOWUP_INTERVAL_DAYS = int(_secret("FOLLOWUP_INTERVAL_DAYS", "3"))

st.set_page_config(page_title="HireGen Outreach Agent", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.step-done { border-left:4px solid #198754 !important; background:#e8f5e9 !important; }
thead tr th { background-color: #f0f2f6 !important; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def log_activity(supabase, event_type, description, lead_id=None):
    supabase.table("activity_log").insert({
        "event_type": event_type,
        "description": description,
        "lead_id": lead_id,
    }).execute()


def save_lead(supabase, lead):
    next_followup = (date.today() + timedelta(days=FOLLOWUP_INTERVAL_DAYS)).isoformat()
    row = {
        "company_name": lead["company_name"],
        "job_title_hiring_for": lead.get("job_title_hiring_for"),
        "job_url": lead.get("job_url"),
        "job_source": lead.get("job_source"),
        "contact_name": lead.get("contact_name"),
        "contact_title": lead.get("contact_title"),
        "contact_email": lead.get("contact_email"),
        "contact_linkedin_url": lead.get("contact_linkedin_url"),
        "status": "new",
        "next_followup_date": next_followup,
    }
    result = supabase.table("leads").insert(row).execute()
    return result.data[0]["id"]


def get_first_name(contact_name: str) -> str | None:
    """Extract first name — returns None if unavailable so template can handle it."""
    if not contact_name or not contact_name.strip():
        return None
    parts = contact_name.strip().split()
    return parts[0] if parts else None


# ── Session state initialisation ──────────────────────────────────────────────
for key, default in {
    "step": 1,
    "discovered_jobs": None,
    "approved_jobs": None,
    "dedup_removed": None,
    "dedup_kept": None,
    "existing_clients_list": [],
    "recently_contacted_count": 0,
    "approved_after_dedup": None,
    "email_template_subject": None,
    "email_template_body": None,
    "followup_templates": None,
    "email_limit": 20,
    "enriched_leads": None,
    "final_leads": None,
    "send_complete": False,
    "active_tab": "Outreach Wizard",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Top-level tabs ─────────────────────────────────────────────────────────────
tab_wizard, tab_history = st.tabs(["🚀 Outreach Wizard", "📋 History"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OUTREACH WIZARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_wizard:
    st.title("🎯 HireGen Outreach Agent")
    st.caption("Human-in-the-loop outreach workflow | susan@hiregen.co")
    st.divider()

    # Progress bar
    steps = ["1. Discover Jobs", "2. Dedup Review", "3. Email Template", "4. Contacts & Send"]
    cols = st.columns(4)
    for i, (col, label) in enumerate(zip(cols, steps), start=1):
        if i < st.session_state.step:
            col.success(f"✅ {label}")
        elif i == st.session_state.step:
            col.info(f"▶️ {label}")
        else:
            col.write(f"⬜ {label}")

    st.divider()

    # ── STEP 1: Job Discovery ─────────────────────────────────────────────────
    if st.session_state.step == 1:
        st.header("Step 1: Discover Today's Jobs")
        st.write("Select job roles and locations, then run the search.")

        col_r, col_l = st.columns(2)
        with col_r:
            selected_roles = st.multiselect(
                "🧑‍💻 Job Roles",
                options=ALL_ROLES,
                default=["Full-stack Developer", "Back-end Developer", "AI Engineer", "Machine Learning Engineer"],
            )
        with col_l:
            selected_locations = st.multiselect(
                "📍 Locations",
                options=ALL_LOCATIONS,
                default=["USA"],
            )

        if selected_roles and selected_locations:
            st.info(f"Will run **{len(selected_roles) * len(selected_locations)} searches** ({len(selected_roles)} roles × {len(selected_locations)} locations)")

        if st.session_state.discovered_jobs is None:
            if st.button("🔍 Run Job Discovery Now", type="primary", use_container_width=True,
                         disabled=not selected_roles or not selected_locations):
                with st.spinner(f"Searching {len(selected_roles) * len(selected_locations)} combinations..."):
                    jobs = discover_jobs(roles=selected_roles, locations=selected_locations)
                    st.session_state.discovered_jobs = jobs
                st.rerun()
        else:
            jobs = st.session_state.discovered_jobs
            st.success(f"Found **{len(jobs)}** companies hiring today.")
            st.subheader("Review & approve companies")

            selected = {}
            header = st.columns([0.5, 2.5, 2.5, 2, 2])
            for h, t in zip(header, ["", "Company", "Job Title", "Location", "Link"]):
                h.markdown(f"**{t}**")
            st.divider()

            for i, job in enumerate(jobs):
                col1, col2, col3, col4, col5 = st.columns([0.5, 2.5, 2.5, 2, 2])
                with col1:
                    selected[i] = st.checkbox("", value=True, key=f"job_{i}")
                with col2:
                    st.write(f"**{job['company_name']}**")
                with col3:
                    st.write(job.get("job_title_hiring_for", "—"))
                with col4:
                    st.write(job.get("location_query", "—"))
                with col5:
                    url = job.get("job_url", "")
                    if url:
                        st.markdown(f"[View Job]({url})")
                    else:
                        st.write(job.get("job_source", "—"))

            st.divider()
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔄 Re-run Discovery", use_container_width=True):
                    st.session_state.discovered_jobs = None
                    st.rerun()
            with col_b:
                approved_count = sum(selected.values())
                if st.button(f"✅ Approve {approved_count} Companies → Next Step",
                             type="primary", use_container_width=True):
                    st.session_state.approved_jobs = [jobs[i] for i, v in selected.items() if v]
                    st.session_state.step = 2
                    st.rerun()

    # ── STEP 2: Dedup Review ──────────────────────────────────────────────────
    elif st.session_state.step == 2:
        st.header("Step 2: Deduplication Review")

        if st.session_state.dedup_kept is None:
            with st.spinner("Checking Google Sheet and outreach history..."):
                jobs = st.session_state.approved_jobs
                existing_clients_set = get_existing_clients()
                already_contacted = get_already_contacted(days=30)
                blocked = existing_clients_set | already_contacted

                removed, kept = [], []
                for job in jobs:
                    key = normalize(job.get("company_name", ""))
                    if key in existing_clients_set:
                        removed.append({**job, "removed_reason": "Existing Client"})
                    elif key in already_contacted:
                        removed.append({**job, "removed_reason": "Contacted in last 30 days"})
                    else:
                        kept.append(job)

                st.session_state.dedup_removed = removed
                st.session_state.dedup_kept = kept
                st.session_state.existing_clients_list = sorted(existing_clients_set)
                st.session_state.recently_contacted_count = len(already_contacted)

        removed = st.session_state.dedup_removed
        kept    = st.session_state.dedup_kept

        # ── Existing clients source verification ─────────────────────────────
        SHEET_URL = os.getenv("GOOGLE_SHEET_URL", "")
        with st.expander("🔍 Verify dedup sources — click to inspect"):
            c_left, c_right = st.columns(2)

            with c_left:
                st.markdown("**📋 Existing Clients (from Google Sheet)**")
                if SHEET_URL:
                    st.markdown(f"[Open Google Sheet ↗]({SHEET_URL})")
                clients_list = st.session_state.get("existing_clients_list", [])
                if clients_list:
                    st.caption(f"{len(clients_list)} companies loaded")
                    for name in sorted(clients_list):
                        st.write(f"• {name}")
                else:
                    st.info("No existing clients found in sheet.")

            with c_right:
                st.markdown("**🕐 Recently Contacted (last 30 days)**")
                recent_count = st.session_state.get("recently_contacted_count", 0)
                st.caption(f"{recent_count} companies contacted in last 30 days — skipped to avoid double outreach.")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"🚫 Removed ({len(removed)})")
            for r in removed:
                icon = "🏢" if r['removed_reason'] == "Existing Client" else "🕐"
                st.markdown(f"- {icon} ~~{r['company_name']}~~ — *{r['removed_reason']}*")
            if not removed:
                st.info("No companies removed.")
        with col2:
            st.subheader(f"✅ Proceeding ({len(kept)})")
            for k in kept:
                st.markdown(f"- **{k['company_name']}** — {k.get('job_title_hiring_for','')}")
            if not kept:
                st.warning("No companies left after dedup.")

        st.divider()
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("← Back", use_container_width=True):
                st.session_state.step = 1
                st.session_state.dedup_kept = None
                st.session_state.dedup_removed = None
                st.rerun()
        with col_b:
            if st.button("🔄 Re-run Dedup", use_container_width=True):
                st.session_state.dedup_kept = None
                st.session_state.dedup_removed = None
                st.rerun()
        with col_c:
            if kept and st.button(f"✅ Confirm {len(kept)} Companies → Next Step",
                                  type="primary", use_container_width=True):
                st.session_state.approved_after_dedup = kept
                st.session_state.step = 3
                st.rerun()

    # ── STEP 3: Email Template ────────────────────────────────────────────────
    elif st.session_state.step == 3:
        st.header("Step 3: Configure Emails & Follow-ups")
        st.info("💡 **Placeholders:** `{first_name}` `{company}` `{role}` — Use the toolbar to **bold**, *italicise*, add hyperlinks, bullet points, and more.")

        # ── How many companies to reach out to ───────────────────────────────
        st.subheader("📊 Outreach Volume")
        available = len(st.session_state.approved_after_dedup or [])
        limit_options = [2, 5, 10, 20, 50, 75, 100, 200]

        email_limit = st.selectbox(
            f"How many companies to contact? ({available} available after dedup)",
            options=limit_options,
            index=3,  # default to 20
        )
        actual = min(email_limit, available)
        st.caption(f"Emails will be sent to **{actual}** companies with random 1–3 min gaps." +
                   (f" *(capped at {available} available)*" if email_limit > available else ""))

        st.divider()

        # ── Intro email ───────────────────────────────────────────────────────
        if st.session_state.email_template_subject is None:
            st.session_state.email_template_subject = EMAIL_TEMPLATES["intro"]["subject"]
        if st.session_state.email_template_body is None:
            st.session_state.email_template_body = EMAIL_TEMPLATES["intro"]["body"]

        st.subheader("📧 Intro Email")
        new_subject = st.text_input("Subject line", value=st.session_state.email_template_subject, key="intro_subject_input")

        st.caption("Email body — use the toolbar for **Bold**, *Italic*, hyperlinks, and lists:")
        new_body = st_quill(
            value=st.session_state.email_template_body,
            placeholder="Write your intro email here...",
            html=True,
            key="intro_body_quill",
        ) or st.session_state.email_template_body

        with st.expander("👁️ Preview intro email"):
            try:
                preview_subject = new_subject.format(first_name="Sarah", company="Acme Corp", role="Full Stack Developer")
                preview_body = new_body.replace("{first_name}", "Sarah").replace("{company}", "Acme Corp").replace("{role}", "Full Stack Developer")
                st.markdown(f"**Subject:** {preview_subject}")
                st.markdown("---")
                st.markdown(preview_body, unsafe_allow_html=True)
            except Exception:
                st.markdown(new_body, unsafe_allow_html=True)

        st.divider()

        # ── Follow-up emails ──────────────────────────────────────────────────
        st.subheader("🔁 Follow-up Emails (sent every 3 days to non-responders)")
        st.caption("Never sent if response is Positive, Negative, or Bounced.")

        if st.session_state.followup_templates is None:
            st.session_state.followup_templates = {
                k: {"subject": v["subject"], "body": v["body"]}
                for k, v in EMAIL_TEMPLATES.items()
                if k.startswith("followup_")
            }

        followup_updates = {}
        for i in range(1, 6):
            key = f"followup_{i}"
            tpl = st.session_state.followup_templates.get(key, EMAIL_TEMPLATES.get(key, {}))
            with st.expander(f"Follow-up #{i} — sent {i * 3} days after intro"):
                fu_subj = st.text_input("Subject", value=tpl.get("subject", ""), key=f"fu_subj_{i}")
                st.caption("Body:")
                fu_body = st_quill(
                    value=tpl.get("body", ""),
                    placeholder=f"Write follow-up #{i} here...",
                    html=True,
                    key=f"fu_quill_{i}",
                ) or tpl.get("body", "")
                followup_updates[key] = {"subject": fu_subj, "body": fu_body}

        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("← Back", use_container_width=True):
                st.session_state.step = 2
                st.rerun()
        with col_b:
            if st.button("✅ Confirm & Find Contacts", type="primary", use_container_width=True):
                st.session_state.email_template_subject = new_subject
                st.session_state.email_template_body = new_body
                st.session_state.followup_templates = followup_updates
                st.session_state.email_limit = min(email_limit, available)
                EMAIL_TEMPLATES["intro"]["subject"] = new_subject
                EMAIL_TEMPLATES["intro"]["body"] = new_body
                for k, v in followup_updates.items():
                    if k in EMAIL_TEMPLATES:
                        EMAIL_TEMPLATES[k]["subject"] = v["subject"]
                        EMAIL_TEMPLATES[k]["body"] = v["body"]
                st.session_state.step = 4
                st.rerun()

    # ── STEP 4: Contacts & Send ───────────────────────────────────────────────
    elif st.session_state.step == 4:
        st.header("Step 4: Review Contacts & Send Emails")

        if st.session_state.enriched_leads is None:
            companies = st.session_state.approved_after_dedup
            limit = min(len(companies), st.session_state.get("email_limit", DAILY_EMAIL_LIMIT))
            st.info(f"Finding contacts for **{limit} companies** via LinkedIn + Wiza. This takes 10–20 minutes. Please wait...")

            progress = st.progress(0)
            status_text = st.empty()
            results = []

            for i, job in enumerate(companies[:limit]):
                status_text.text(f"Looking up {job['company_name']}... ({i+1}/{limit})")
                from agent.contact_finder import prospect_contact
                contact = prospect_contact(job["company_name"])
                if contact:
                    job.update(contact)
                else:
                    job["contact_email"] = None
                results.append(job)
                progress.progress((i + 1) / limit)

            st.session_state.enriched_leads = results
            status_text.text("✅ Contact lookup complete!")
            st.rerun()

        else:
            leads = st.session_state.enriched_leads
            found = [l for l in leads if l.get("contact_email")]
            not_found = [l for l in leads if not l.get("contact_email")]

            st.success(f"✅ Found contacts for **{len(found)}** companies. ❌ No contact for **{len(not_found)}** (will be skipped).")

            if not_found:
                with st.expander(f"❌ {len(not_found)} companies skipped (no contact found)"):
                    for l in not_found:
                        st.write(f"- {l['company_name']}")

            st.subheader("Review each contact — uncheck to skip")

            # Warn about missing names
            no_name = [l for l in found if not get_first_name(l.get("contact_name", ""))]
            if no_name:
                st.warning(f"⚠️ {len(no_name)} contact(s) have no name — they are unchecked by default. Verify before sending.")

            # Column headers
            hcols = st.columns([0.5, 2, 2, 2, 2, 1.5])
            for hc, ht in zip(hcols, ["Send?", "Company", "Full Name", "Email", "LinkedIn Profile", "Title"]):
                hc.markdown(f"**{ht}**")
            st.divider()

            send_flags = {}
            for i, lead in enumerate(found):
                col1, col2, col3, col4, col5, col6 = st.columns([0.5, 2, 2, 2, 2, 1.5])
                has_name = bool(get_first_name(lead.get("contact_name", "")))

                with col1:
                    # Default unchecked if no name
                    send_flags[i] = st.checkbox("", value=has_name, key=f"send_{i}")
                with col2:
                    st.write(f"**{lead['company_name']}**")
                with col3:
                    name = lead.get("contact_name") or "—"
                    if not has_name:
                        st.markdown(f"⚠️ *{name}*")
                    else:
                        st.write(name)
                with col4:
                    st.write(lead.get("contact_email", "—"))
                with col5:
                    linkedin = lead.get("contact_linkedin_url", "")
                    if linkedin:
                        st.markdown(f"[🔗 View LinkedIn Profile]({linkedin})")
                    else:
                        st.write("—")
                with col6:
                    st.caption(lead.get("contact_title", ""))

                with st.expander(f"Preview email → {lead.get('contact_name') or lead['company_name']}"):
                    subj, body = render_template("intro", lead)
                    st.markdown(f"**Subject:** {subj}")
                    st.text(body)
                    if not has_name:
                        st.error("⚠️ No first name found — email will say 'Hi there'. Uncheck this contact or find their name manually.")

                st.divider()

            approved_leads = [found[i] for i, v in send_flags.items() if v]

            # ── Campaign name ─────────────────────────────────────────────────
            if approved_leads and not st.session_state.send_complete:
                st.divider()
                default_name = datetime.now(PACIFIC).strftime("Campaign — %b %d, %Y %I:%M %p PT")
                campaign_name_input = st.text_input(
                    "📛 Campaign Name",
                    value=default_name,
                    help="Auto-generated from date & time. Edit to give this campaign a custom name.",
                    key="campaign_name_input"
                )

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button("← Back to Step 3", use_container_width=True):
                    st.session_state.step = 3
                    st.session_state.enriched_leads = None
                    st.rerun()
            with col_b:
                if st.button("🔄 Re-run Contact Lookup", use_container_width=True):
                    st.session_state.enriched_leads = None
                    st.rerun()
            with col_c:
                if approved_leads and not st.session_state.send_complete:
                    if st.button(f"🚀 Schedule {len(approved_leads)} Emails",
                                 type="primary", use_container_width=True):
                        supabase = get_supabase()
                        now = datetime.now(timezone.utc)
                        now_pt = now.astimezone(PACIFIC)
                        delay_seconds = 0
                        schedule_preview = []

                        # Use user-edited name or fall back to auto-generated
                        campaign_id = str(uuid.uuid4())
                        campaign_name = st.session_state.get("campaign_name_input") or f"Campaign — {now_pt.strftime('%b %d, %Y %I:%M %p PT')}"

                        for i, lead in enumerate(approved_leads):
                            if i > 0:
                                gap = random.randint(60, 180)
                                delay_seconds += gap
                            send_at = now + timedelta(seconds=delay_seconds)

                            lead_id = save_lead(supabase, lead)
                            lead_with_id = {**lead, "lead_id": lead_id}

                            supabase.table("email_queue").insert({
                                "lead_data": lead_with_id,
                                "email_type": "intro",
                                "scheduled_for": send_at.isoformat(),
                                "status": "pending",
                                "campaign_id": campaign_id,
                                "campaign_name": campaign_name,
                            }).execute()

                            schedule_preview.append({
                                "name": lead.get("contact_name", "—"),
                                "company": lead["company_name"],
                                "send_at": send_at.astimezone(PACIFIC).strftime("%I:%M:%S %p PT"),
                            })

                        log_activity(supabase, "agent_run",
                                     f"{len(approved_leads)} emails scheduled. Campaign: {campaign_name}")
                        st.session_state.send_complete = True
                        st.session_state.final_leads = approved_leads
                        st.session_state.schedule_preview = schedule_preview
                        st.session_state.current_campaign_id = campaign_id

                        total_mins = delay_seconds // 60
                        st.success(f"🗓️ **{len(approved_leads)} emails scheduled!** Over ~{total_mins} mins with random 1–3 min gaps.")
                        st.info("⚠️ Make sure the **scheduler is running** (`python3 scheduler.py`) — it sends emails even after you close this app.")
                        st.balloons()

            if st.session_state.send_complete:
                st.success(f"✅ {len(st.session_state.final_leads)} emails queued and will be sent automatically.")

                # Show schedule preview
                if hasattr(st.session_state, "schedule_preview") and st.session_state.get("schedule_preview"):
                    with st.expander("📅 View send schedule"):
                        for item in st.session_state.schedule_preview:
                            st.write(f"🕐 **{item['send_at']}** → {item['name']} @ {item['company']}")

                st.warning("Make sure `python3 scheduler.py` is running in your terminal to deliver the emails.")

                if st.button("🔁 Start a New Outreach Run", type="primary", use_container_width=True):
                    for key in ["discovered_jobs", "approved_jobs", "dedup_removed", "dedup_kept",
                                "approved_after_dedup", "email_template_subject", "email_template_body",
                                "enriched_leads", "final_leads"]:
                        st.session_state[key] = None
                    st.session_state.step = 1
                    st.session_state.send_complete = False
                    st.rerun()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("📊 Pipeline Overview")
        try:
            supabase = get_supabase()
            leads = supabase.table("leads").select("status").execute().data
            by_status = {}
            for l in leads:
                s = l["status"]
                by_status[s] = by_status.get(s, 0) + 1

            st.metric("Total Leads", len(leads))
            for status, count in by_status.items():
                st.write(f"**{status.title()}:** {count}")

            st.divider()
            st.subheader("⏰ Follow-ups Due")
            today = date.today().isoformat()
            due = supabase.table("leads").select("company_name, contact_name, followup_count") \
                .in_("status", ["emailed", "following_up"]) \
                .lte("next_followup_date", today).execute().data
            if due:
                st.warning(f"{len(due)} follow-up(s) due today!")
                for d in due[:5]:
                    st.write(f"- {d['company_name']} (follow-up #{d['followup_count']+1})")
                if st.button("Send Today's Follow-ups"):
                    from main import send_followups
                    count = send_followups(get_supabase(), 0)
                    st.success(f"Sent {count} follow-ups!")
            else:
                st.success("No follow-ups due today.")
        except Exception:
            st.info("No data yet.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PAST CAMPAIGNS
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.title("📋 Past Campaigns")

    if st.button("🔄 Refresh", key="refresh_history"):
        st.rerun()

    try:
        from collections import defaultdict
        supabase = get_supabase()

        all_emails = supabase.table("emails_sent") \
            .select("id, lead_id, email_type, to_email, to_name, subject, sent_at, gmail_message_id") \
            .order("sent_at", desc=True).execute().data

        all_leads = supabase.table("leads") \
            .select("id, company_name, contact_name, contact_email, contact_linkedin_url, contact_title, status") \
            .execute().data

        leads_map = {l["id"]: l for l in all_leads}

        # ── All-time summary stats ────────────────────────────────────────────
        st.subheader("📊 All-Time Summary")
        total_companies = len({e["lead_id"] for e in all_emails if e.get("lead_id")})
        total_people    = len({e["to_email"] for e in all_emails if e.get("to_email")})
        intro_emails    = len([e for e in all_emails if e.get("email_type") == "intro"])
        followup_emails = len([e for e in all_emails if e.get("email_type", "").startswith("followup")])
        success_emails  = len([e for e in all_emails if e.get("gmail_message_id")])
        replied         = len([l for l in all_leads if l.get("status") == "replied"])

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("🏢 Companies", total_companies)
        c2.metric("👤 People", total_people)
        c3.metric("📧 Intros Sent", intro_emails)
        c4.metric("🔁 Follow-ups", followup_emails)
        c5.metric("✅ Delivered", success_emails)
        c6.metric("💬 Replied", replied)

        st.divider()

        # ── Pending queue ─────────────────────────────────────────────────────
        try:
            queue = supabase.table("email_queue").select("*").order("scheduled_for").execute().data
            pending = [q for q in queue if q["status"] == "pending"]
            if pending:
                q_col1, q_col2 = st.columns([4, 1])
                with q_col1:
                    st.subheader(f"⏳ Emails Pending in Queue ({len(pending)})")
                with q_col2:
                    if st.button("🛑 Cancel All Pending", type="secondary", use_container_width=True):
                        for item in pending:
                            supabase.table("email_queue").update({"status": "cancelled"}).eq("id", item["id"]).execute()
                        st.success(f"✅ {len(pending)} pending emails cancelled.")
                        st.rerun()

                rows = []
                for item in pending:
                    lead = item.get("lead_data", {})
                    sched = item.get("scheduled_for", "")
                    campaign = item.get("campaign_name", "—")
                    try:
                        sched_dt = datetime.fromisoformat(sched.replace("Z", "+00:00")).astimezone(PACIFIC)
                        time_str = sched_dt.strftime("%I:%M %p PT")
                    except Exception:
                        time_str = "—"
                    rows.append({
                        "Scheduled For": time_str,
                        "Campaign": campaign,
                        "Company": lead.get("company_name", "—"),
                        "Contact": lead.get("contact_name", "—"),
                        "Email": lead.get("contact_email", "—"),
                        "Type": item.get("email_type", "intro").replace("_", " ").title(),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                st.divider()
        except Exception:
            pass

        # ── Campaigns grouped by campaign_id ──────────────────────────────────
        if not all_emails:
            st.info("No campaigns yet. Complete your first outreach run in the Wizard tab.")
        else:
            st.subheader("📅 Past Campaigns")
            st.caption("Each outreach run is a separate campaign. Click to expand.")

            RESPONSE_OPTIONS = ["⏳ Pending", "🟢 Positive Response", "🔴 Negative Response", "⚪ Email Bounced", "🟡 Other"]
            RESPONSE_MAP = {"⏳ Pending": None, "🟢 Positive Response": "positive", "🔴 Negative Response": "negative", "⚪ Email Bounced": "bounced", "🟡 Other": "other"}
            RESPONSE_REVERSE = {v: k for k, v in RESPONSE_MAP.items()}
            EMAIL_TYPE_LABELS = {"intro": "📧 Intro", "followup_1": "🔁 Follow-up 1", "followup_2": "🔁 Follow-up 2", "followup_3": "🔁 Follow-up 3", "followup_4": "🔁 Follow-up 4", "followup_5": "🔁 Follow-up 5"}

            def fmt_dt(ts):
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(PACIFIC).strftime("%b %d, %I:%M %p PT")
                except Exception:
                    return ts[:16] if ts else "—"

            def fmt_time(ts):
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(PACIFIC).strftime("%I:%M %p PT")
                except Exception:
                    return "—"

            # Build leads → all emails map for pending calculation
            lead_emails_map = defaultdict(list)
            for e in all_emails:
                if e.get("lead_id"):
                    lead_emails_map[e["lead_id"]].append(e)

            # Group by campaign_id (fall back to date if no campaign_id)
            by_campaign = defaultdict(list)
            for email in all_emails:
                cid = email.get("campaign_id") or f"date_{email.get('sent_at','')[:10]}"
                by_campaign[cid].append(email)

            # Sort campaigns by first email time desc
            sorted_campaigns = sorted(
                by_campaign.items(),
                key=lambda x: min((e.get("sent_at","") for e in x[1]), default=""),
                reverse=True
            )

            for cid, c_emails in sorted_campaigns:
                intros      = [e for e in c_emails if e.get("email_type") == "intro"]
                followups   = [e for e in c_emails if e.get("email_type","").startswith("followup")]
                delivered   = [e for e in c_emails if e.get("gmail_message_id")]
                failed      = [e for e in c_emails if not e.get("gmail_message_id")]
                companies_ct= len({e["lead_id"] for e in c_emails if e.get("lead_id")})
                people_ct   = len({e["to_email"] for e in c_emails if e.get("to_email")})
                success_rate= f"{round(len(delivered)/len(c_emails)*100)}%" if c_emails else "—"

                # Get campaign name
                sample = c_emails[0]
                camp_name = sample.get("campaign_name") or fmt_dt(sample.get("sent_at",""))

                with st.expander(
                    f"🚀 **{camp_name}** &nbsp;|&nbsp; "
                    f"👤 {people_ct} people &nbsp;|&nbsp; "
                    f"📧 {len(intros)} intros &nbsp;|&nbsp; "
                    f"🔁 {len(followups)} follow-ups &nbsp;|&nbsp; "
                    f"✅ {success_rate} delivered"
                ):
                    mc1, mc2, mc3, mc4, mc5 = st.columns([2, 2, 2, 2, 3])
                    mc1.metric("People Reached", people_ct)
                    mc2.metric("Companies", companies_ct)
                    mc3.metric("Delivered", len(delivered))
                    mc4.metric("Failed", len(failed))
                    with mc5:
                        new_camp_name = st.text_input(
                            "✏️ Rename Campaign",
                            value=camp_name,
                            key=f"rename_{cid}",
                            label_visibility="collapsed",
                            placeholder="Rename this campaign..."
                        )
                        if new_camp_name != camp_name and st.button("Save name", key=f"save_name_{cid}"):
                            try:
                                supabase.table("email_queue").update({"campaign_name": new_camp_name}).eq("campaign_id", cid).execute()
                                supabase.table("emails_sent").update({"campaign_name": new_camp_name}).eq("campaign_id", cid).execute() if hasattr(supabase.table("emails_sent"), "campaign_name") else None
                                st.success("✅ Campaign renamed!")
                                st.rerun()
                            except Exception:
                                pass
                    st.markdown("---")

                    # Headers
                    hdr = st.columns([1.5, 1.8, 2.2, 2.0, 2.2, 2.5, 2.0])
                    for h, t in zip(hdr, ["Company", "Full Name & LinkedIn", "Email", "Emails Sent", "Pending Emails", "Response", "✓"]):
                        h.markdown(f"**{t}**")
                    st.markdown("---")

                    # Group by lead within this campaign — one row per lead
                    campaign_leads = {}
                    for email in sorted(c_emails, key=lambda x: x.get("sent_at", "")):
                        lid = email.get("lead_id") or email.get("to_email", "")
                        if lid not in campaign_leads:
                            campaign_leads[lid] = {"emails": [], "lead": leads_map.get(email.get("lead_id"), {})}
                        campaign_leads[lid]["emails"].append(email)

                    for lid, ldata in campaign_leads.items():
                        lead   = ldata["lead"]
                        emails = ldata["emails"]
                        name   = (emails[0].get("to_name") or lead.get("contact_name") or "—")
                        linkedin = lead.get("contact_linkedin_url", "")
                        company = lead.get("company_name") or "—"
                        lead_id = lead.get("id")
                        current_response = lead.get("response_status")
                        snippet = lead.get("response_snippet", "")

                        # Emails sent string: "📧 Intro — May 31 9:45 AM\n🔁 Follow-up 1 — Jun 3 10:02 AM"
                        sent_lines = []
                        for e in emails:
                            label = EMAIL_TYPE_LABELS.get(e.get("email_type",""), e.get("email_type",""))
                            dt_str = fmt_dt(e.get("sent_at",""))
                            icon = "✅" if e.get("gmail_message_id") else "❌"
                            sent_lines.append(f"{icon} {label} — {dt_str}")

                        # Pending emails: calculate upcoming follow-ups
                        followup_count = lead.get("followup_count", 0) or 0
                        next_followup_date = lead.get("next_followup_date")
                        pending_lines = []
                        if lead.get("status") in ("emailed", "following_up") and \
                           lead.get("response_status") not in ("positive","negative","bounced") and \
                           followup_count < 5 and next_followup_date:
                            try:
                                next_dt = datetime.fromisoformat(next_followup_date).replace(tzinfo=timezone.utc)
                                for i in range(followup_count + 1, 6):
                                    label = EMAIL_TYPE_LABELS.get(f"followup_{i}", f"Follow-up {i}")
                                    days_offset = (i - followup_count - 1) * 3
                                    send_date = next_dt + timedelta(days=days_offset)
                                    pending_lines.append(f"⏳ {label} — {send_date.astimezone(PACIFIC).strftime('%b %d')}")
                            except Exception:
                                pass

                        all_status = "✅" if all(e.get("gmail_message_id") for e in emails) else "⚠️"

                        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 1.8, 2.0, 2.2, 2.5, 2.0, 1.0])
                        c1.write(f"**{company}**")
                        if linkedin:
                            c2.markdown(f"[{name}]({linkedin}) 🔗")
                        else:
                            c2.write(name)
                        c3.write(emails[0].get("to_email","—"))
                        c4.markdown("\n\n".join(sent_lines) if sent_lines else "—")
                        c5.markdown("\n\n".join(pending_lines) if pending_lines else "✅ All done")
                        c7.write(all_status)

                        if lead_id:
                            current_label = RESPONSE_REVERSE.get(current_response, "⏳ Pending")
                            new_label = c6.selectbox(
                                "", RESPONSE_OPTIONS,
                                index=RESPONSE_OPTIONS.index(current_label) if current_label in RESPONSE_OPTIONS else 0,
                                key=f"resp_{lead_id}_{cid}",
                                label_visibility="collapsed"
                            )
                            new_val = RESPONSE_MAP[new_label]
                            if new_val != current_response:
                                try:
                                    upd = {"response_status": new_val}
                                    if new_val == "positive":
                                        upd["status"] = "replied"
                                    supabase.table("leads").update(upd).eq("id", lead_id).execute()
                                    lead["response_status"] = new_val
                                except Exception:
                                    pass
                            if snippet and current_response:
                                c6.caption(f"💬 {snippet[:50]}...")
                        else:
                            c6.write("—")
                        st.divider()

    except Exception as e:
        st.error(f"Could not load campaigns: {e}")
        import traceback
        st.code(traceback.format_exc())
