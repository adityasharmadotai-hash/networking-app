import os
from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client

from agent.job_discovery import discover_jobs
from agent.contact_finder import enrich_leads
from agent.dedup import filter_leads
from agent.email_sender import send_email, render_template, FOLLOWUP_SEQUENCE

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
DAILY_EMAIL_LIMIT = int(os.getenv("DAILY_EMAIL_LIMIT", 20))
FOLLOWUP_INTERVAL_DAYS = int(os.getenv("FOLLOWUP_INTERVAL_DAYS", 3))
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", 5))


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def log_activity(supabase, event_type: str, description: str, lead_id: str = None):
    supabase.table("activity_log").insert({
        "event_type": event_type,
        "description": description,
        "lead_id": lead_id,
    }).execute()


def save_lead(supabase, lead: dict) -> str:
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
    }
    result = supabase.table("leads").insert(row).execute()
    return result.data[0]["id"]


def send_intro_emails(supabase, leads: list[dict], emails_sent_today: int) -> int:
    """Send intro emails to new leads. Returns updated email count."""
    for lead in leads:
        if emails_sent_today >= DAILY_EMAIL_LIMIT:
            print(f"[Main] Daily email limit of {DAILY_EMAIL_LIMIT} reached.")
            break

        if lead.get("status") == "skipped" or not lead.get("contact_email"):
            continue

        print(f"[Main] Saving lead: {lead['company_name']}")
        lead_id = save_lead(supabase, lead)

        subject, body = render_template("intro", lead)
        gmail_id = send_email(lead["contact_email"], subject, body)

        if gmail_id:
            next_followup = (date.today() + timedelta(days=FOLLOWUP_INTERVAL_DAYS)).isoformat()
            supabase.table("leads").update({
                "status": "emailed",
                "followup_count": 0,
                "next_followup_date": next_followup,
                "last_contacted_at": "now()",
            }).eq("id", lead_id).execute()

            supabase.table("emails_sent").insert({
                "lead_id": lead_id,
                "email_type": "intro",
                "to_email": lead["contact_email"],
                "to_name": lead.get("contact_name"),
                "subject": subject,
                "body": body,
                "gmail_message_id": gmail_id,
            }).execute()

            log_activity(supabase, "email_sent",
                         f"Intro email sent to {lead.get('contact_name')} at {lead['company_name']}",
                         lead_id)
            emails_sent_today += 1
            print(f"[Main] Intro sent to {lead.get('contact_email')} ({lead['company_name']})")

    return emails_sent_today


def send_followups(supabase, emails_sent_today: int) -> int:
    """Send scheduled follow-up emails. Returns updated email count."""
    today = date.today().isoformat()

    result = supabase.table("leads") \
        .select("*") \
        .in_("status", ["emailed", "following_up"]) \
        .lte("next_followup_date", today) \
        .lt("followup_count", MAX_FOLLOWUPS) \
        .execute()

    due_leads = result.data
    print(f"[Main] {len(due_leads)} follow-ups due today.")

    for lead in due_leads:
        if emails_sent_today >= DAILY_EMAIL_LIMIT:
            print(f"[Main] Daily email limit reached during follow-ups.")
            break

        followup_num = lead["followup_count"] + 1
        template_key = f"followup_{followup_num}"

        if template_key not in FOLLOWUP_SEQUENCE:
            continue

        subject, body = render_template(template_key, lead)
        gmail_id = send_email(lead["contact_email"], subject, body)

        if gmail_id:
            next_followup = (date.today() + timedelta(days=FOLLOWUP_INTERVAL_DAYS)).isoformat()
            new_status = "following_up" if followup_num < MAX_FOLLOWUPS else "closed"

            supabase.table("leads").update({
                "status": new_status,
                "followup_count": followup_num,
                "next_followup_date": next_followup if new_status != "closed" else None,
                "last_contacted_at": "now()",
            }).eq("id", lead["id"]).execute()

            supabase.table("emails_sent").insert({
                "lead_id": lead["id"],
                "email_type": template_key,
                "to_email": lead["contact_email"],
                "to_name": lead.get("contact_name"),
                "subject": subject,
                "body": body,
                "gmail_message_id": gmail_id,
            }).execute()

            log_activity(supabase, "followup_sent",
                         f"Follow-up #{followup_num} sent to {lead.get('contact_name')} at {lead['company_name']}",
                         lead["id"])
            emails_sent_today += 1
            print(f"[Main] Follow-up #{followup_num} sent to {lead['contact_email']}")

    return emails_sent_today


def run_agent():
    print(f"\n{'='*50}")
    print(f"[Main] Starting outreach agent — {date.today()}")
    print(f"{'='*50}\n")

    supabase = get_supabase()
    emails_sent_today = 0

    # Step 1: Send due follow-ups first (priority)
    print("[Main] === Step 1: Sending follow-up emails ===")
    emails_sent_today = send_followups(supabase, emails_sent_today)

    # Step 2: Discover new jobs
    print("\n[Main] === Step 2: Discovering new jobs ===")
    jobs = discover_jobs()

    # Step 3: Filter out existing clients and already-contacted companies
    print("\n[Main] === Step 3: Deduplication ===")
    filtered_jobs = filter_leads(jobs)

    # Step 4: Find contacts via Wiza
    print("\n[Main] === Step 4: Finding contacts via Wiza ===")
    enriched_leads = enrich_leads(filtered_jobs)

    # Step 5: Send intro emails (up to daily limit)
    print("\n[Main] === Step 5: Sending intro emails ===")
    emails_sent_today = send_intro_emails(supabase, enriched_leads, emails_sent_today)

    print(f"\n[Main] Done. Total emails sent today: {emails_sent_today}")
    log_activity(supabase, "agent_run",
                 f"Agent completed. {emails_sent_today} emails sent.")


if __name__ == "__main__":
    run_agent()
