"""
digest.py -- Saturday-only. Generate weekly digest via Claude, update snapshot, send via Buttondown.
"""

import json
import logging
import os
import sys
from datetime import date, timedelta

import anthropic
import requests
from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
BUTTONDOWN_API_KEY = os.environ["BUTTONDOWN_API_KEY"]

SYSTEM_PROMPT = """
You are writing the weekly digest for The PM Adaptation Index, an empirical observatory
tracking how AI is reshaping the product management profession.

Your job: write exactly 3-4 sentences that:
1. Report the headline numbers (total postings, AI penetration rate) with WoW comparison
2. Call out the top AI skill(s) that dominated PM job postings this week
3. Name the leading companies hiring PMs with AI skills if the pattern is noteworthy
4. Interpret the signal honestly against the central thesis. If data is inconclusive, say so.

Tone: a curious, honest reporter. Not a cheerleader. Not an alarmist.
Do not editorialize beyond the data. Never use em dashes.
"""


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def fetch_snapshots(supabase: Client, since: date, until: date) -> list[dict]:
    resp = (
        supabase.table("daily_snapshots")
        .select("*")
        .gte("snapshot_date", str(since))
        .lte("snapshot_date", str(until))
        .order("snapshot_date")
        .execute()
    )
    return resp.data


def generate_digest(payload: dict) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=350,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Generate the digest for this data: {json.dumps(payload, default=str)}",
            }
        ],
    )
    return response.content[0].text.strip()


def send_digest_email(subject: str, body: str):
    resp = requests.post(
        "https://api.buttondown.email/v1/emails",
        headers={"Authorization": f"Token {BUTTONDOWN_API_KEY}"},
        json={
            "subject": subject,
            "body": body,
            "status": "about_to_send",
        },
        timeout=30,
    )
    resp.raise_for_status()
    log.info(f"Email sent via Buttondown: {resp.status_code}")


def main():
    if date.today().weekday() != 5:  # 5 = Saturday
        log.info("Not Saturday -- digest skipped")
        sys.exit(0)

    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    supabase = get_supabase()
    snapshots = fetch_snapshots(supabase, seven_days_ago, today)

    if not snapshots:
        log.warning("No snapshots found for the past 7 days. Skipping digest.")
        sys.exit(0)

    latest = snapshots[-1]
    snapshot_7d_ago = snapshots[0] if len(snapshots) > 1 else None

    top_employers = latest.get("top_employers_ai_skills") or {}
    companies_top5 = (top_employers.get("companies") or [])[:5]

    payload = {
        "snapshot_date": latest["snapshot_date"],
        "total_postings": latest.get("total_postings"),
        "total_postings_7day_avg": latest.get("total_postings_7day_avg"),
        "ai_penetration_rate": latest.get("ai_penetration_rate"),
        "ai_penetration_7days_ago": snapshot_7d_ago.get("ai_penetration_rate") if snapshot_7d_ago else None,
        "top_ai_skills": latest.get("top_ai_skills"),
        "top_employers_ai_skills": {"companies": companies_top5},
        "days_of_data": len(snapshots),
    }

    log.info("Calling Claude API for digest generation...")
    summary_text = generate_digest(payload)
    log.info(f"Digest generated ({len(summary_text)} chars)")

    # Update the Saturday snapshot with the digest
    supabase.table("daily_snapshots").update(
        {
            "summary_text": summary_text,
            "digest_generated_at": "now()",
        }
    ).eq("snapshot_date", str(today)).execute()
    log.info(f"Snapshot updated for {today}")

    # Send email
    week_label = today.strftime("%B %-d, %Y")
    subject = f"PM Adaptation Index: Week of {week_label}"
    send_digest_email(subject, summary_text)

    log.info("Digest complete.")


if __name__ == "__main__":
    main()
