"""
fetch_employers.py -- Pull PM listings directly from curated employer job boards.

Covers AI-native companies (Anthropic, OpenAI, DeepMind, xAI, etc.) that Adzuna
and JSearch don't reliably index because they post on their own ATS.

Supports:
  - Greenhouse (https://boards-api.greenhouse.io/v1/boards/{slug}/jobs)
  - Ashby      (https://api.ashbyhq.com/posting-api/job-board/{slug})

Reads pipeline/data/employer_boards.csv for the curated company list.
Writes one fetch_log row per ATS source ('greenhouse', 'ashby').
posted_date = first-seen date (the day this pipeline first ingested the job).
"""

import csv
import html
import logging
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

DATA_DIR = Path(__file__).parent.parent / "data"

# PM-titled patterns -- mirrors enrich.py title patterns.
# Match any of these substrings (case-insensitive) in the job title.
PM_TITLE_PATTERNS = [
    "product manager",
    "product management",   # "Product Management, Human Data Platform" -style titles
    "product lead",
    "head of product",
    "director of product",
    "director, product",
    "vp of product",
    "vp product",
    "vice president of product",
    "chief product officer",
    "group product manager",
    "principal product",
    "staff product",
    "senior product",
    "associate product manager",
    "junior product manager",
]

# Exclusions: titles that contain "product" but are not PM roles.
# Tested against the title BEFORE the PM_TITLE_PATTERNS check.
PM_TITLE_EXCLUSIONS = [
    "product designer",
    "product marketing",
    "product support",
    "product analyst",
    "data engineering manager, product",
    "engineering manager, product",
    "engineering manager, vertical ai products",
    "incident response manager",
    "software engineer",
    "research engineer",
    "developer productivity",
    "new product introduction",
]


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def is_pm_title(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    if any(ex in t for ex in PM_TITLE_EXCLUSIONS):
        return False
    return any(p in t for p in PM_TITLE_PATTERNS)


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_boards() -> list[dict]:
    rows = []
    with open(DATA_DIR / "employer_boards.csv", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def fetch_greenhouse_board(session: requests.Session, slug: str) -> list[dict]:
    """Return all jobs from a Greenhouse board with content."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    resp = session.get(url, params={"content": "true"}, timeout=60)
    resp.raise_for_status()
    return resp.json().get("jobs", [])


def fetch_ashby_board(session: requests.Session, slug: str) -> list[dict]:
    """Return all jobs from an Ashby job board."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    resp = session.get(url, params={"includeCompensation": "true"}, timeout=60)
    resp.raise_for_status()
    return resp.json().get("jobs", [])


def to_raw_record_greenhouse(job: dict, company: str, today: date) -> dict:
    return {
        "source": "greenhouse",
        "source_id": str(job["id"]),
        "title": job.get("title"),
        "company": company,
        "location": (job.get("location") or {}).get("name"),
        # posted_date = first-seen date (today). The unique constraint preserves
        # the original posted_date on subsequent runs.
        "posted_date": str(today),
        "run_date": str(today),
        "description_text": strip_html(job.get("content") or ""),
        "url": job.get("absolute_url"),
        "is_remote": None,
        "raw_payload": job,
    }


def to_raw_record_ashby(job: dict, company: str, today: date) -> dict:
    return {
        "source": "ashby",
        "source_id": str(job["id"]),
        "title": job.get("title"),
        "company": company,
        "location": job.get("location"),
        "posted_date": str(today),
        "run_date": str(today),
        "description_text": strip_html(
            job.get("descriptionPlain") or job.get("descriptionHtml") or ""
        ),
        "url": job.get("jobUrl"),
        "is_remote": job.get("isRemote"),
        "raw_payload": job,
    }


def fetch_source(
    supabase: Client,
    source: str,
    boards: list[dict],
    today: date,
) -> dict:
    """Fetch all boards for a given ATS source. Returns aggregate stats."""
    session = requests.Session()
    records_fetched = 0
    records_inserted = 0
    records_skipped = 0
    errors = []

    relevant = [b for b in boards if b["ats"] == source]

    for board in relevant:
        company = board["company"]
        slug = board["slug"]
        try:
            time.sleep(0.5)  # polite pacing
            if source == "greenhouse":
                jobs = fetch_greenhouse_board(session, slug)
                converter = to_raw_record_greenhouse
            elif source == "ashby":
                jobs = fetch_ashby_board(session, slug)
                converter = to_raw_record_ashby
            else:
                raise ValueError(f"Unknown source: {source}")

            pm_jobs = [j for j in jobs if is_pm_title(j.get("title", ""))]
            log.info(f"  {company} ({slug}): {len(jobs)} total, {len(pm_jobs)} PM")

            for job in pm_jobs:
                records_fetched += 1
                record = converter(job, company, today)
                if not record["source_id"]:
                    records_skipped += 1
                    continue

                resp = (
                    supabase.table("job_postings_raw")
                    .upsert(
                        record,
                        on_conflict="source,source_id",
                        ignore_duplicates=True,
                    )
                    .execute()
                )
                if resp.data:
                    records_inserted += 1
                else:
                    records_skipped += 1

        except Exception as e:
            log.error(f"  {company} ({slug}) failed: {e}")
            errors.append(f"{company}: {e}")

    if records_fetched == 0 and errors:
        status = "failed"
    elif errors:
        status = "partial"
    else:
        status = "ok"

    return {
        "source": source,
        "records_fetched": records_fetched,
        "records_inserted": records_inserted,
        "records_skipped": records_skipped,
        "status": status,
        "error_message": "; ".join(errors)[:1000] if errors else None,
    }


def write_fetch_log(supabase: Client, run_date: date, result: dict):
    record = {
        "run_date": str(run_date),
        "source": result["source"],
        "records_fetched": result["records_fetched"],
        "records_inserted": result["records_inserted"],
        "records_skipped": result["records_skipped"],
        "adzuna_total_count": None,
        "status": result["status"],
        "error_message": result.get("error_message"),
    }
    supabase.table("fetch_log").upsert(record, on_conflict="run_date,source").execute()
    log.info(
        f"fetch_log written: source={result['source']} status={result['status']} "
        f"inserted={result['records_inserted']} skipped={result['records_skipped']}"
    )


def main():
    # Align with fetch.py: write fetch_log + posted_date as `yesterday`
    # so the aggregator (which runs for target_date=yesterday) picks up
    # today's freshly-ingested rows.
    run_date = date.today() - timedelta(days=1)
    log.info(f"Starting employer-board fetch for run_date={run_date}")

    supabase = get_supabase()
    boards = load_boards()
    log.info(f"Loaded {len(boards)} curated employer boards")

    sources = sorted({b["ats"] for b in boards})
    failed = []
    for source in sources:
        log.info(f"--- Fetching {source} boards ---")
        result = fetch_source(supabase, source, boards, run_date)
        write_fetch_log(supabase, run_date, result)
        if result["status"] == "failed":
            failed.append(source)

    if failed:
        log.error(f"Sources failed: {failed}. Exiting non-zero.")
        sys.exit(1)


if __name__ == "__main__":
    main()
