"""
fetch.py -- Pull PM job listings from Adzuna and JSearch for the previous 24 hours.

Writes raw records to job_postings_raw (dedup via UNIQUE constraint).
Writes one fetch_log row per source per run.
Exits non-zero if either source has status='failed'.
"""

import os
import sys
import time
import logging
from datetime import date, timedelta

import requests
from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ADZUNA_APP_ID = os.environ["ADZUNA_APP_ID"]
ADZUNA_APP_KEY = os.environ["ADZUNA_APP_KEY"]
JSEARCH_API_KEY = os.environ["JSEARCH_API_KEY"]

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/us/search"
JSEARCH_BASE = "https://jsearch.p.rapidapi.com/search"


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def yesterday() -> date:
    return date.today() - timedelta(days=1)


def adzuna_request(session: requests.Session, path: str, params: dict, retries: int = 1):
    """Single Adzuna API call with one retry on 429."""
    url = f"{ADZUNA_BASE}/{path}"
    for attempt in range(retries + 1):
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            if attempt < retries:
                log.warning("Adzuna rate-limited. Waiting 60s before retry.")
                time.sleep(60)
                continue
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()
    return None


def fetch_adzuna(supabase: Client, run_date: date) -> dict:
    """
    Fetch new PM postings from Adzuna for yesterday.
    Also fetches the total live count via a single-result call.
    Returns a fetch result dict.
    """
    yesterday_iso = run_date.strftime("%Y-%m-%d")
    session = requests.Session()

    records_fetched = 0
    records_inserted = 0
    records_skipped = 0
    adzuna_total_count = None
    errors = []

    base_params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": "product manager",
        "results_per_page": 50,
        "max_days_old": 1,
        "sort_by": "date",
    }

    # Fetch total live count (page 1, results_per_page=1)
    try:
        count_params = {k: v for k, v in base_params.items() if k != "date_from"}
        count_params["results_per_page"] = 1
        count_data = adzuna_request(session, "1", count_params)
        adzuna_total_count = count_data.get("count")
        log.info(f"Adzuna total live PM postings: {adzuna_total_count}")
    except Exception as e:
        log.error(f"Adzuna total count fetch failed: {e}")
        errors.append(str(e))

    # Paginate new postings
    page = 1
    while True:
        try:
            time.sleep(1)  # 1 req/sec rate limit
            data = adzuna_request(session, str(page), base_params)
            results = data.get("results", [])
            if not results:
                break

            for job in results:
                records_fetched += 1
                source_id = str(job.get("id", ""))
                if not source_id:
                    records_skipped += 1
                    continue

                raw_record = {
                    "source": "adzuna",
                    "source_id": source_id,
                    "title": job.get("title"),
                    "company": job.get("company", {}).get("display_name"),
                    "location": job.get("location", {}).get("display_name"),
                    "posted_date": job.get("created", "")[:10] or None,
                    "run_date": str(run_date),
                    "description_text": (job.get("description") or "")[:2000],
                    "url": job.get("redirect_url"),
                    "is_remote": None,
                    "raw_payload": job,
                }

                resp = (
                    supabase.table("job_postings_raw")
                    .upsert(raw_record, on_conflict="source,source_id", ignore_duplicates=True)
                    .execute()
                )
                if resp.data:
                    records_inserted += 1
                else:
                    records_skipped += 1

            page += 1
            if page > 20:  # safety cap
                break

        except Exception as e:
            log.error(f"Adzuna page {page} error: {e}")
            errors.append(str(e))
            break

    if records_inserted == 0 and errors:
        status = "failed"
    elif errors:
        status = "partial"
    else:
        status = "ok"

    return {
        "source": "adzuna",
        "records_fetched": records_fetched,
        "records_inserted": records_inserted,
        "records_skipped": records_skipped,
        "adzuna_total_count": adzuna_total_count,
        "status": status,
        "error_message": "; ".join(errors) if errors else None,
    }


def jsearch_request(session: requests.Session, params: dict, retries: int = 1):
    """Single JSearch API call with one retry on 429."""
    headers = {"X-RapidAPI-Key": JSEARCH_API_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    for attempt in range(retries + 1):
        resp = session.get(JSEARCH_BASE, params=params, headers=headers, timeout=60)
        if resp.status_code == 429:
            if attempt < retries:
                log.warning("JSearch rate-limited. Waiting 60s before retry.")
                time.sleep(60)
                continue
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()
    return None


def fetch_jsearch(supabase: Client, run_date: date) -> dict:
    """Fetch new PM postings from JSearch for today."""
    session = requests.Session()

    records_fetched = 0
    records_inserted = 0
    records_skipped = 0
    errors = []

    for page_num in range(1, 4):  # 3 pages max
        try:
            time.sleep(1)
            params = {
                "query": "product manager in united states",
                "page": str(page_num),
                "num_pages": "1",
                "date_posted": "today",
            }
            data = jsearch_request(session, params)
            jobs = data.get("data", [])
            if not jobs:
                break

            for job in jobs:
                records_fetched += 1
                source_id = job.get("job_id", "")
                if not source_id:
                    records_skipped += 1
                    continue

                posted_raw = job.get("job_posted_at_datetime_utc", "")
                posted_date = posted_raw[:10] if posted_raw else str(run_date)

                raw_record = {
                    "source": "jsearch",
                    "source_id": source_id,
                    "title": job.get("job_title"),
                    "company": job.get("employer_name"),
                    "location": " ".join(
                        filter(None, [job.get("job_city"), job.get("job_state")])
                    ),
                    "posted_date": posted_date,
                    "run_date": str(run_date),
                    "description_text": job.get("job_description") or "",
                    "url": job.get("job_apply_link"),
                    "is_remote": job.get("job_is_remote"),
                    "raw_payload": job,
                }

                resp = (
                    supabase.table("job_postings_raw")
                    .upsert(raw_record, on_conflict="source,source_id", ignore_duplicates=True)
                    .execute()
                )
                if resp.data:
                    records_inserted += 1
                else:
                    records_skipped += 1

        except Exception as e:
            log.error(f"JSearch page {page_num} error: {e}")
            errors.append(str(e))

    if records_inserted == 0 and errors:
        status = "failed"
    elif errors:
        status = "partial"
    else:
        status = "ok"

    return {
        "source": "jsearch",
        "records_fetched": records_fetched,
        "records_inserted": records_inserted,
        "records_skipped": records_skipped,
        "adzuna_total_count": None,
        "status": status,
        "error_message": "; ".join(errors) if errors else None,
    }


def write_fetch_log(supabase: Client, run_date: date, result: dict):
    record = {
        "run_date": str(run_date),
        "source": result["source"],
        "records_fetched": result["records_fetched"],
        "records_inserted": result["records_inserted"],
        "records_skipped": result["records_skipped"],
        "adzuna_total_count": result.get("adzuna_total_count"),
        "status": result["status"],
        "error_message": result.get("error_message"),
    }
    supabase.table("fetch_log").upsert(record, on_conflict="run_date,source").execute()
    log.info(
        f"fetch_log written: source={result['source']} status={result['status']} "
        f"inserted={result['records_inserted']} skipped={result['records_skipped']}"
    )


def main():
    run_date = yesterday()
    log.info(f"Starting fetch for run_date={run_date}")

    supabase = get_supabase()

    adzuna_result = fetch_adzuna(supabase, run_date)
    write_fetch_log(supabase, run_date, adzuna_result)

    jsearch_result = fetch_jsearch(supabase, run_date)
    write_fetch_log(supabase, run_date, jsearch_result)

    log.info(
        f"Fetch complete. Adzuna: {adzuna_result['status']}, JSearch: {jsearch_result['status']}"
    )

    if adzuna_result["status"] == "failed" or jsearch_result["status"] == "failed":
        log.error("One or more sources failed. Exiting non-zero to fail the pipeline.")
        sys.exit(1)


if __name__ == "__main__":
    main()
