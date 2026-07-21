"""
Daily auto-discovery loop
-------------------------
Runs once each morning (via GitHub Actions). Discovers today's jobs, dedups,
finds *verified* contacts, drafts personalized intros, and queues them as
`awaiting_approval` — then emails the approver a summary.

Nothing sends automatically: everything waits in the dashboard's Approvals tab
until the approver clicks Approve. This is the "act → observe → self-correct →
after my approval" loop, with the human gate kept in place.

Run:   python daily_discover.py
"""

import os
import uuid
import random
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from supabase import create_client

from agent.job_discovery import discover_jobs
from agent.dedup import get_existing_clients, get_already_contacted, normalize
from agent.contact_finder import prospect_contact
from agent.suppression import get_unsubscribed_emails
from agent.email_sender import send_email

load_dotenv()

PACIFIC = ZoneInfo("America/Los_Angeles")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
APPROVER_EMAIL = os.getenv("APPROVER_EMAIL", "devrajsolanki33@gmail.com")
FOLLOWUP_INTERVAL_DAYS = int(os.getenv("FOLLOWUP_INTERVAL_DAYS", "3"))

# How many verified contacts to queue per day (keeps volume + API cost in check).
DAILY_NEW_LEADS = int(os.getenv("DAILY_NEW_LEADS", "10"))
ROLES = [r.strip() for r in os.getenv(
    "DISCOVER_ROLES",
    "Full-stack Developer,Back-end Developer,AI Engineer,Machine Learning Engineer",
).split(",") if r.strip()]
LOCATIONS = [l.strip() for l in os.getenv("DISCOVER_LOCATIONS", "USA").split(",") if l.strip()]


def _sb():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _next_send_slot(dt_utc):
    """Earliest datetime >= dt_utc inside the 8am-6pm PT weekday window."""
    pt = dt_utc.astimezone(PACIFIC)
    for _ in range(14):
        if pt.weekday() >= 5:
            pt = (pt + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        elif pt.hour < 8:
            pt = pt.replace(hour=8, minute=0, second=0, microsecond=0)
        elif pt.hour >= 18:
            pt = (pt + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        else:
            break
    return pt.astimezone(timezone.utc)


def _save_lead(sb, lead) -> str:
    next_followup = (datetime.now(timezone.utc).date() + timedelta(days=FOLLOWUP_INTERVAL_DAYS)).isoformat()
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
    return sb.table("leads").insert(row).execute().data[0]["id"]


def run_daily_discovery():
    sb = _sb()
    print(f"[Daily] {datetime.now(PACIFIC):%Y-%m-%d %I:%M %p PT} — discovering jobs for {ROLES} in {LOCATIONS}")

    jobs = discover_jobs(roles=ROLES, locations=LOCATIONS)
    print(f"[Daily] {len(jobs)} jobs discovered")

    blocked = get_existing_clients() | get_already_contacted(days=30)
    kept = [j for j in jobs if normalize(j.get("company_name", "")) not in blocked]
    print(f"[Daily] {len(kept)} companies after dedup")

    suppressed = get_unsubscribed_emails()
    campaign_id = str(uuid.uuid4())
    campaign_name = "Auto — " + datetime.now(PACIFIC).strftime("%b %d, %Y")
    send_at = _next_send_slot(datetime.now(timezone.utc))
    queued = []

    for job in kept:
        if len(queued) >= DAILY_NEW_LEADS:
            break
        contact = prospect_contact(job["company_name"])   # already domain-verified
        if not contact:
            continue
        email = (contact.get("contact_email") or "").strip().lower()
        if not email or email in suppressed:
            print(f"[Daily] Skipped (no email / suppressed): {job['company_name']}")
            continue

        lead = {**job, **contact}
        lead_id = _save_lead(sb, lead)
        lead_data = {**lead, "lead_id": lead_id, "followup_count": 0}
        if queued:
            send_at = _next_send_slot(send_at + timedelta(seconds=random.randint(60, 180)))

        sb.table("email_queue").insert({
            "lead_data": lead_data,
            "email_type": "intro",
            "scheduled_for": send_at.isoformat(),
            "status": "awaiting_approval",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
        }).execute()
        queued.append(lead)
        print(f"[Daily] ✅ Queued for approval: {lead['company_name']} -> {email}")

    # Summary email to the approver
    if queued:
        lines = "\n".join(
            f"  • {l['company_name']} — {l.get('contact_name','?')} <{l.get('contact_email')}>"
            for l in queued
        )
        body = (
            f"Good morning,\n\n{len(queued)} new outreach email(s) were auto-discovered and are "
            f"waiting for your approval (campaign: {campaign_name}):\n\n{lines}\n\n"
            "Open the HireGen dashboard → Approvals tab to Approve, Reject, or leave for later. "
            "Nothing sends until you approve it.\n\n— HireGen"
        )
        try:
            send_email(APPROVER_EMAIL, f"[HireGen] {len(queued)} new emails to approve", body)
            print(f"[Daily] Summary emailed to {APPROVER_EMAIL}")
        except Exception as e:
            print(f"[Daily] Summary email failed: {e}")
    else:
        print("[Daily] Nothing new to queue today.")

    print(f"[Daily] Done. {len(queued)} queued for approval.")
    return len(queued)


if __name__ == "__main__":
    run_daily_discovery()
