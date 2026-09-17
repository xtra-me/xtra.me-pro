"""
Run this on a schedule (cron / Render Cron Job / GitHub Actions schedule):
  - morning run: once per day, per user's morning time
  - daytime run: 1-2x per day

For the free test phase, simplest setup: two scheduled triggers hitting
this script — e.g. `python email_job.py morning` and `python email_job.py daytime`.
"""
import os
import sys
from datetime import datetime, timedelta
import requests
from supabase import create_client
from groq import Groq

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
FROM_EMAIL = os.environ.get("FROM_EMAIL", "axel@yourdomain.com")

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

ACTIVE_WINDOW_HOURS = 3  # if user active on site within this window, skip email


def is_user_active(user_id: str) -> bool:
    # Assumes a `last_seen` column you update from the frontend on activity.
    res = sb.table("org_members").select("last_seen").eq("user_id", user_id).execute().data
    if not res or not res[0].get("last_seen"):
        return False
    last_seen = datetime.fromisoformat(res[0]["last_seen"])
    return datetime.utcnow() - last_seen < timedelta(hours=ACTIVE_WINDOW_HOURS)


def send_email(to: str, subject: str, html: str):
    requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={"from": FROM_EMAIL, "to": [to], "subject": subject, "html": html},
    )


def build_context(org_member_id: str) -> str:
    from main import get_member_context  # reuse existing logic
    return get_member_context(org_member_id)


def run(mode: str):
    members = sb.table("org_members").select("*, users:user_id(email)").execute().data
    for m in members:
        if not m.get("groq_api_key"):
            continue
        if is_user_active(m["user_id"]):
            continue

        context = build_context(m["id"])
        client = Groq(api_key=m["groq_api_key"])

        if mode == "morning":
            prompt = (
                "Write a short, warm good-morning email for this person. Include a "
                "genuine, personal-feeling greeting/well-wish, then a clear, friendly "
                "summary of today's priorities based on their context below. Keep it "
                "concise, not corporate.\n\n" + context
            )
            subject = "Good morning — here's your day"
        else:
            prompt = (
                "Write a brief, friendly check-in nudge email mentioning anything "
                "due today or overdue, based on this context. Keep it short.\n\n" + context
            )
            subject = "Quick check-in"

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        body_text = completion.choices[0].message.content
        email = m.get("users", {}).get("email") if m.get("users") else None
        if not email:
            continue

        send_email(email, subject, f"<div>{body_text.replace(chr(10), '<br>')}</div>")

        sb.table("ai_messages").insert({
            "org_member_id": m["id"], "role": "assistant",
            "content": body_text, "origin": "email"
        }).execute()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "daytime")
