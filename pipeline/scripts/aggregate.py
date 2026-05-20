"""
aggregate.py -- Read enriched records for yesterday, compute daily metrics, upsert into daily_snapshots.

Usage:
  python aggregate.py [--date YYYY-MM-DD]
"""

import argparse
import logging
import os
from collections import Counter
from datetime import date, timedelta
from typing import Optional

from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
PIPELINE_VERSION = "v1.0"

# Sources used for AI signal (full-text descriptions). Adzuna is excluded
# because its descriptions are truncated.
FULL_TEXT_SOURCES = ["jsearch", "greenhouse", "ashby"]


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def fetch_all_rows(build_query, page_size: int = 1000) -> list[dict]:
    """Page through a PostgREST query so results are not silently capped at
    1000 rows. build_query must return a fresh query builder on each call."""
    rows: list[dict] = []
    offset = 0
    while True:
        page = build_query().range(offset, offset + page_size - 1).execute().data
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def yesterday() -> date:
    return date.today() - timedelta(days=1)


def rolling_7day_avg(supabase: Client, column: str, target_date: date) -> Optional[float]:
    """
    Average of `column` for the 7 days strictly before target_date.
    Returns None if fewer than 3 rows of data.
    Strict upper bound (< target_date) ensures idempotency when reprocessing earlier dates.
    """
    since = target_date - timedelta(days=7)
    resp = (
        supabase.table("daily_snapshots")
        .select(f"snapshot_date,{column}")
        .gte("snapshot_date", str(since))
        .lt("snapshot_date", str(target_date))
        .not_.is_(column, "null")
        .order("snapshot_date", desc=True)
        .limit(7)
        .execute()
    )
    rows = resp.data
    if len(rows) < 3:
        return None
    values = [float(r[column]) for r in rows if r[column] is not None]
    return sum(values) / len(values) if values else None


def _batched_in(supabase, table: str, columns: str, ids: list, batch_size: int = 100,
                extra_eq: Optional[tuple] = None) -> list[dict]:
    """Run a .in_('id', ids) query in batches to avoid URL length limits."""
    out = []
    for i in range(0, len(ids), batch_size):
        batch = ids[i : i + batch_size]
        q = supabase.table(table).select(columns)
        if extra_eq:
            for col, val in extra_eq:
                q = q.eq(col, val)
        q = q.in_("id" if table == "job_postings_raw" else "raw_id", batch)
        out.extend(q.execute().data)
    return out


def fetch_enriched_full_text(supabase: Client, target_date: date) -> list[dict]:
    """All enriched records for target_date from full-text sources (JSearch+Greenhouse+Ashby)."""
    raw_rows = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .eq("posted_date", str(target_date))
        .in_("source", FULL_TEXT_SOURCES)
        .order("id")
    )
    raw_ids = [r["id"] for r in raw_rows]
    if not raw_ids:
        return []
    return _batched_in(
        supabase,
        "job_postings_enriched",
        "raw_id,dedup_hash,has_ai_requirement,ai_keyword_matches,company_normalized",
        raw_ids,
        extra_eq=(("pipeline_version", PIPELINE_VERSION),),
    )


def fetch_enriched_full_text_range(
    supabase: Client, since: date, before: date
) -> list[dict]:
    """All enriched full-text records in [since, before)."""
    raw_rows = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id,posted_date")
        .gte("posted_date", str(since))
        .lt("posted_date", str(before))
        .in_("source", FULL_TEXT_SOURCES)
        .order("id")
    )
    raw_ids = [r["id"] for r in raw_rows]
    raw_date_map = {r["id"]: r["posted_date"] for r in raw_rows}
    if not raw_ids:
        return []
    enriched = _batched_in(
        supabase,
        "job_postings_enriched",
        "raw_id,dedup_hash,has_ai_requirement,ai_keyword_matches,company_normalized",
        raw_ids,
        extra_eq=(("pipeline_version", PIPELINE_VERSION),),
    )
    for row in enriched:
        row["posted_date"] = raw_date_map.get(row["raw_id"])
    return enriched


def skill_direction(kw: str, count: int, prev_total: int, days: int, ever_seen: set) -> str:
    if kw not in ever_seen:
        return "new"
    if days == 0 or prev_total == 0:
        return "rising"
    prev_daily_avg = prev_total / days
    if count >= prev_daily_avg * 1.15:
        return "rising"
    if count <= prev_daily_avg * 0.85:
        return "falling"
    return "flat"


def company_direction(current_count: int, prev_count: int) -> str:
    # 'new' check MUST come first -- otherwise prev=0 always hits 'up'
    if prev_count == 0:
        return "new"
    if current_count > prev_count:
        return "up"
    if current_count < prev_count:
        return "down"
    return "flat"


def count_companies(records: list[dict]) -> dict[str, int]:
    """Dedup by dedup_hash within the window, group by normalized company."""
    out: dict[str, set] = {}
    for r in records:
        company = r.get("company_normalized") or ""
        if not company:
            continue
        out.setdefault(company, set()).add(r.get("dedup_hash"))
    return {company: len(hashes) for company, hashes in out.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else yesterday()
    log.info(f"Aggregating for target_date={target_date}")

    supabase = get_supabase()

    # ── 0. PARTIAL-FAILURE PROPAGATION ──────────────────────────────────────────
    EXPECTED_SOURCES = ["adzuna", "jsearch", "greenhouse", "ashby"]
    logs_resp = (
        supabase.table("fetch_log")
        .select("*")
        .eq("run_date", str(target_date))
        .in_("source", EXPECTED_SOURCES)
        .execute()
    )
    logs_by_source = {row["source"]: row for row in logs_resp.data}
    adzuna_log = logs_by_source.get("adzuna")
    jsearch_log = logs_by_source.get("jsearch")

    data_quality_notes = []
    missing = [s for s in EXPECTED_SOURCES if s not in logs_by_source]
    partial = [s for s, l in logs_by_source.items() if l["status"] == "partial"]
    failed_logs = [s for s, l in logs_by_source.items() if l["status"] == "failed"]

    if missing or failed_logs:
        data_quality_status = "degraded"
        for s in missing:
            data_quality_notes.append(f"{s} fetch log missing")
        for s in failed_logs:
            data_quality_notes.append(f"{s} failed: {logs_by_source[s].get('error_message', '')}")
    elif partial:
        data_quality_status = "partial"
        for s in partial:
            data_quality_notes.append(f"{s} partial: {logs_by_source[s].get('error_message', '')}")
    else:
        data_quality_status = "complete"

    log.info(f"data_quality_status={data_quality_status}")

    # ── 1. VOLUME (Adzuna live count) ────────────────────────────────────────────
    total_postings = adzuna_log["adzuna_total_count"] if adzuna_log else None
    new_postings_today = adzuna_log["records_inserted"] if adzuna_log else None

    # ── 2. ROLLING AVERAGES ───────────────────────────────────────────────────────
    total_postings_7day_avg = rolling_7day_avg(supabase, "total_postings", target_date)
    new_postings_7day_avg = rolling_7day_avg(supabase, "new_postings_today", target_date)

    # ── 3. AI PENETRATION RATE (daily rate, JSearch only) ────────────────────────
    todays_full_text = fetch_enriched_full_text(supabase, target_date)
    distinct_hashes = {r["dedup_hash"] for r in todays_full_text if r.get("dedup_hash")}
    ai_hashes = {
        r["dedup_hash"]
        for r in todays_full_text
        if r.get("has_ai_requirement") and r.get("dedup_hash")
    }
    total_today = len(distinct_hashes)
    ai_today = len(ai_hashes)

    ai_penetration_rate = (ai_today / total_today * 100) if total_today > 0 else None
    ai_penetration_7day_avg = rolling_7day_avg(supabase, "ai_penetration_rate", target_date)

    log.info(
        f"AI penetration: {ai_today}/{total_today} = {ai_penetration_rate:.1f}%"
        if ai_penetration_rate is not None
        else "AI penetration: no data"
    )

    # ── 4. TOP 10 AI SKILLS TODAY ────────────────────────────────────────────────
    todays_ai_records = [r for r in todays_full_text if r.get("has_ai_requirement")]
    keyword_counts: Counter = Counter()
    for record in todays_ai_records:
        for kw in (record.get("ai_keyword_matches") or []):
            keyword_counts[kw] += 1
    top_10_today = keyword_counts.most_common(10)

    # Prior 7-day records for trend comparison
    prior_start = target_date - timedelta(days=7)
    prior_records = fetch_enriched_full_text_range(supabase, prior_start, target_date)
    prior_ai_records = [r for r in prior_records if r.get("has_ai_requirement")]

    prev_7day_counts: Counter = Counter()
    prior_dates = set()
    for record in prior_ai_records:
        for kw in (record.get("ai_keyword_matches") or []):
            prev_7day_counts[kw] += 1
        if record.get("posted_date"):
            prior_dates.add(record["posted_date"])
    prev_7day_days_with_data = len(prior_dates)

    # All-time seen keywords (for 'new' detection)
    ever_seen_rows = fetch_all_rows(
        lambda: supabase.table("job_postings_enriched")
        .select("ai_keyword_matches")
        .eq("pipeline_version", PIPELINE_VERSION)
        .eq("has_ai_requirement", True)
        .order("raw_id")
    )
    ever_seen: set[str] = set()
    for row in ever_seen_rows:
        for kw in (row.get("ai_keyword_matches") or []):
            ever_seen.add(kw)
    # Also include the prior 7-day keywords so recently-seen aren't labeled 'new'
    ever_seen |= set(prev_7day_counts.keys())

    top_ai_skills = {
        "total_ai_postings_today": len(todays_ai_records),
        "skills": [
            {
                "rank": i + 1,
                "keyword": kw,
                "count": count,
                "prev_7day_daily_avg": round(
                    prev_7day_counts.get(kw, 0) / max(prev_7day_days_with_data, 1), 1
                ),
                "direction": skill_direction(
                    kw, count,
                    prev_7day_counts.get(kw, 0),
                    prev_7day_days_with_data,
                    ever_seen,
                ),
            }
            for i, (kw, count) in enumerate(top_10_today)
        ],
    }

    # ── 5. TOP 10 COMPANIES (7-day rolling window, inclusive of target_date) ───
    # Window: [target_date - 6, target_date + 1) = 7 days ending on target_date.
    # Prior:  [target_date - 13, target_date - 6) = preceding 7-day window.
    # Idempotent for reprocessing because we never reference future dates.
    seven_day_start = target_date - timedelta(days=6)
    seven_day_records = fetch_enriched_full_text_range(supabase, seven_day_start, target_date + timedelta(days=1))
    seven_day_ai = [r for r in seven_day_records if r.get("has_ai_requirement")]

    prior_window_start = target_date - timedelta(days=13)
    prior_window_end = target_date - timedelta(days=6)
    prior_window_records = fetch_enriched_full_text_range(supabase, prior_window_start, prior_window_end)
    prior_window_ai = [r for r in prior_window_records if r.get("has_ai_requirement")]

    current_total = count_companies(seven_day_records)
    current_ai = count_companies(seven_day_ai)
    prior_total = count_companies(prior_window_records)
    prior_ai = count_companies(prior_window_ai)
    # Rank by total PM openings; AI-requiring subset shown as share within bar.
    top_10_companies = sorted(current_total.items(), key=lambda x: x[1], reverse=True)[:10]

    top_employers_ai_skills = {
        "window_days": 7,
        "window_end": str(target_date),
        "companies": [
            {
                "rank": i + 1,
                "company": company,
                "total_count": total_count,
                "ai_count": current_ai.get(company, 0),
                "count": current_ai.get(company, 0),  # backward compat
                "ai_pct": round(current_ai.get(company, 0) / total_count * 100) if total_count > 0 else 0,
                "prev_total_count": prior_total.get(company, 0),
                "prev_count": prior_ai.get(company, 0),
                "direction": company_direction(total_count, prior_total.get(company, 0)),
            }
            for i, (company, total_count) in enumerate(top_10_companies)
        ],
    }

    # ── 6. DEDUP QUALITY ─────────────────────────────────────────────────────────
    all_raw_today = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .eq("posted_date", str(target_date))
        .order("id")
    )
    all_raw_ids_today = [r["id"] for r in all_raw_today]
    total_postings_raw = len(all_raw_ids_today)

    if all_raw_ids_today:
        all_enriched_today = _batched_in(
            supabase,
            "job_postings_enriched",
            "dedup_hash",
            all_raw_ids_today,
            extra_eq=(("pipeline_version", PIPELINE_VERSION),),
        )
        hashes_today = {r["dedup_hash"] for r in all_enriched_today if r.get("dedup_hash")}
        distinct_today = len(hashes_today)
    else:
        distinct_today = 0

    dedup_rate = (
        (total_postings_raw - distinct_today) / total_postings_raw * 100
        if total_postings_raw > 0
        else 0.0
    )

    # ── 7. UPSERT ─────────────────────────────────────────────────────────────────
    snapshot = {
        "snapshot_date": str(target_date),
        "computed_at": "now()",
        "pipeline_version": PIPELINE_VERSION,
        "data_quality_status": data_quality_status,
        "data_quality_notes": "; ".join(data_quality_notes) if data_quality_notes else None,
        "total_postings": total_postings,
        "total_postings_7day_avg": total_postings_7day_avg,
        "new_postings_today": new_postings_today,
        "new_postings_7day_avg": new_postings_7day_avg,
        "ai_penetration_rate": round(ai_penetration_rate, 2) if ai_penetration_rate is not None else None,
        "ai_penetration_7day_avg": round(ai_penetration_7day_avg, 2) if ai_penetration_7day_avg is not None else None,
        "total_postings_raw": total_postings_raw,
        "dedup_rate": round(dedup_rate, 2),
        "top_ai_skills": top_ai_skills,
        "top_employers_ai_skills": top_employers_ai_skills,
        # summary_text and digest_generated_at are intentionally excluded from the upsert
        # so Saturday's digest is never overwritten by a later reprocessing run
    }

    # Use raw upsert that preserves summary_text and digest_generated_at
    existing = (
        supabase.table("daily_snapshots")
        .select("summary_text,digest_generated_at")
        .eq("snapshot_date", str(target_date))
        .execute()
    )
    if existing.data:
        existing_row = existing.data[0]
        snapshot["summary_text"] = existing_row.get("summary_text")
        snapshot["digest_generated_at"] = existing_row.get("digest_generated_at")

    supabase.table("daily_snapshots").upsert(snapshot, on_conflict="snapshot_date").execute()

    log.info(
        f"Snapshot upserted for {target_date}: "
        f"total_postings={total_postings} ai_rate={ai_penetration_rate} "
        f"dedup_rate={dedup_rate:.1f}%"
    )


if __name__ == "__main__":
    main()
