"""
HireGen Email Scheduler
-----------------------
Persistent background process that:
  1. Sends queued emails on schedule (every 30s check)
  2. Sends follow-up emails (every 3 days to non-responders)
  3. Checks Gmail inbox for replies (every 4 hours)

All emails only fire between 8:00 AM – 6:00 PM Pacific Time.

Start:           python3 scheduler.py
Run in background: nohup python3 scheduler.py > scheduler.log 2>&1 &
"""

import os
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from supabase import create_client
from agent.email_sender import send_email, render_template

load_dotenv()

SUPABASE_URL            = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
POLL_INTERVAL           = 30            # seconds between queue checks
REPLY_CHECK_INTERVAL    = 4 * 3600      # check replies every 4 hours
FOLLOWUP_INTERVAL_DAYS  = 3
MAX_FOLLOWUPS           = 5
PACIFIC                 = ZoneInfo("America/Los_Angeles")
SEND_HOUR_START         = 8             # 8 AM Pacific
SEND_HOUR_END           = 18            # 6 PM Pacific
DAILY_EMAIL_LIMIT       = int(os.getenv("DAILY_EMAIL_LIMIT", "20"))  # max sends per PT day
PER_RUN_LIMIT           = int(os.getenv("PER_RUN_LIMIT", "5"))       # max sends per run (avoid Gmail bursts)

_last_reply_check = 0


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def is_send_window() -> bool:
    """Returns True if current Pacific time is between 8 AM and 6 PM."""
    now_pt = datetime.now(PACIFIC)
    return SEND_HOUR_START <= now_pt.hour < SEND_HOUR_END


def process_queue():
    """Send any queued emails that are due — only within send window."""
    if not is_send_window():
        return 0

    supabase = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    result = supabase.table("email_queue") \
        .select("*") \
        .eq("status", "pending") \
        .lte("scheduled_for", now) \
        .order("scheduled_for") \
        .execute()

    due = result.data
    if not due:
        return 0

    # Respect a daily cap (per Pacific day) and a per-run cap so we never burst
    # past Gmail's sending limit. Anything over the cap stays pending for later.
    start_pt = datetime.now(PACIFIC).replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_pt.astimezone(timezone.utc).isoformat()
    sent_today_res = supabase.table("email_queue").select("id", count="exact") \
        .eq("status", "sent").gte("sent_at", start_utc).execute()
    already_today = sent_today_res.count or 0
    daily_remaining = max(0, DAILY_EMAIL_LIMIT - already_today)
    batch_size = min(len(due), PER_RUN_LIMIT, daily_remaining)

    if batch_size <= 0:
        print(f"[Scheduler] Daily limit reached ({already_today}/{DAILY_EMAIL_LIMIT}) — "
              f"holding {len(due)} email(s) for tomorrow.")
        return 0

    batch = due[:batch_size]
    print(f"[Scheduler] {len(due)} due; sending {len(batch)} this run "
          f"(today {already_today}/{DAILY_EMAIL_LIMIT}, per-run cap {PER_RUN_LIMIT})...")
    sent = 0

    for item in batch:
        lead       = item["lead_data"]
        email_type = item.get("email_type", "intro")

        try:
            subject, body = render_template(email_type, lead)
            gmail_id = send_email(lead["contact_email"], subject, body)

            if not gmail_id:
                # Send failed (often a Gmail rate/limit error) — stop this run so
                # we don't hammer the limit; the rest stay pending for next run.
                print("[Scheduler] ⚠️ A send returned no id (possible Gmail limit) — "
                      "stopping this run; remaining emails stay pending.")
                break

            if gmail_id:
                supabase.table("email_queue").update({
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "gmail_message_id": gmail_id,
                }).eq("id", item["id"]).execute()

                if lead.get("lead_id"):
                    supabase.table("emails_sent").insert({
                        "lead_id": lead["lead_id"],
                        "email_type": email_type,
                        "to_email": lead["contact_email"],
                        "to_name": lead.get("contact_name"),
                        "subject": subject,
                        "body": body,
                        "gmail_message_id": gmail_id,
                        "campaign_id": item.get("campaign_id"),
                    }).execute()

                    followup_count = lead.get("followup_count", 0)
                    next_followup  = (datetime.now(timezone.utc) + timedelta(days=FOLLOWUP_INTERVAL_DAYS)).date().isoformat()
                    new_status     = "following_up" if email_type.startswith("followup") else "emailed"

                    supabase.table("leads").update({
                        "status": new_status,
                        "last_contacted_at": datetime.now(timezone.utc).isoformat(),
                        "followup_count": followup_count + (1 if email_type.startswith("followup") else 0),
                        "next_followup_date": next_followup,
                    }).eq("id", lead["lead_id"]).execute()

                sent += 1
                print(f"[Scheduler] ✅ [{email_type}] {lead.get('contact_name')} @ {lead.get('company_name')}")

            else:
                supabase.table("email_queue").update({
                    "status": "failed",
                    "error_message": "Gmail returned no message ID",
                }).eq("id", item["id"]).execute()
                print(f"[Scheduler] ❌ Failed: {lead.get('company_name')}")

        except Exception as e:
            supabase.table("email_queue").update({
                "status": "failed",
                "error_message": str(e),
            }).eq("id", item["id"]).execute()
            print(f"[Scheduler] ❌ Error: {lead.get('company_name')}: {e}")

    return sent


def schedule_followups():
    """
    Find leads due for a follow-up and queue them.
    Only for leads with no response, or response = 'other'.
    Skip: positive, negative, bounced.
    """
    if not is_send_window():
        return 0

    supabase = get_supabase()
    today    = datetime.now(timezone.utc).date().isoformat()

    result = supabase.table("leads") \
        .select("*") \
        .in_("status", ["emailed", "following_up"]) \
        .lte("next_followup_date", today) \
        .lt("followup_count", MAX_FOLLOWUPS) \
        .execute()

    due_leads = [
        l for l in result.data
        if l.get("response_status") not in ("positive", "negative", "bounced")
    ]

    if not due_leads:
        return 0

    print(f"[Scheduler] 🔁 {len(due_leads)} follow-up(s) due today.")
    queued = 0
    delay  = 0

    for lead in due_leads:
        followup_num  = (lead.get("followup_count") or 0) + 1
        email_type    = f"followup_{followup_num}"
        gap           = __import__("random").randint(60, 180)
        delay        += gap
        send_at       = datetime.now(timezone.utc) + timedelta(seconds=delay)

        lead_data = {
            "lead_id":              lead["id"],
            "company_name":         lead.get("company_name"),
            "contact_name":         lead.get("contact_name"),
            "contact_email":        lead.get("contact_email"),
            "contact_title":        lead.get("contact_title"),
            "contact_linkedin_url": lead.get("contact_linkedin_url"),
            "job_title_hiring_for": lead.get("job_title_hiring_for"),
            "followup_count":       followup_num - 1,
        }

        supabase.table("email_queue").insert({
            "lead_data":     lead_data,
            "email_type":    email_type,
            "scheduled_for": send_at.isoformat(),
            "status":        "pending",
        }).execute()

        print(f"[Scheduler] 📅 Queued {email_type} for {lead.get('contact_name')} @ {lead.get('company_name')}")
        queued += 1

    return queued


def run():
    global _last_reply_check

    print("=" * 55)
    print("HireGen Email Scheduler")
    print(f"  • Queue check:    every {POLL_INTERVAL}s")
    print(f"  • Follow-ups:     every {POLL_INTERVAL}s (when due)")
    print(f"  • Reply check:    every {REPLY_CHECK_INTERVAL // 3600}h")
    print(f"  • Send window:    {SEND_HOUR_START}:00 AM – {SEND_HOUR_END % 12}:00 PM Pacific")
    print("  Press Ctrl+C to stop")
    print("=" * 55)

    while True:
        try:
            now_pt = datetime.now(PACIFIC)

            if is_send_window():
                sent    = process_queue()
                queued  = schedule_followups()
                if sent:
                    print(f"[Scheduler] ✅ {sent} email(s) sent.")
                if queued:
                    print(f"[Scheduler] 📅 {queued} follow-up(s) queued.")
            else:
                print(f"[Scheduler] 🌙 Outside send window ({now_pt.strftime('%I:%M %p PT')}) — sleeping.")

            # Reply check every 4 hours
            now_ts = time.time()
            if now_ts - _last_reply_check >= REPLY_CHECK_INTERVAL:
                print("[Scheduler] 📬 Checking Gmail for replies...")
                try:
                    from agent.reply_checker import check_all_replies
                    updated = check_all_replies()
                    print(f"[Scheduler] 📬 {updated} leads updated with reply status.")
                except Exception as re:
                    print(f"[Scheduler] Reply check error: {re}")
                _last_reply_check = now_ts

        except Exception as e:
            print(f"[Scheduler] Error: {e}")

        time.sleep(POLL_INTERVAL)


def run_once():
    """Single pass — for GitHub Actions / cron (free, no always-on worker needed).
    Sends due queued emails, queues due follow-ups, and checks for replies, then exits.
    The 8am–6pm PT send window is still enforced by process_queue/schedule_followups."""
    print(f"[Scheduler] Single run — {datetime.now(PACIFIC).strftime('%Y-%m-%d %I:%M %p PT')}")
    try:
        sent = process_queue()
        queued = schedule_followups()
        print(f"[Scheduler] ✅ {sent} sent, 📅 {queued} follow-up(s) queued.")
    except Exception as e:
        print(f"[Scheduler] Send error: {e}")

    try:
        from agent.reply_checker import check_all_replies
        updated = check_all_replies()
        print(f"[Scheduler] 📬 {updated} lead(s) updated with reply status.")
    except Exception as e:
        print(f"[Scheduler] Reply check error: {e}")


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        run_once()
    else:
        run()
