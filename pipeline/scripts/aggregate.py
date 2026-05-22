"""
aggregate.py -- Read enriched records for yesterday, compute daily metrics, upsert into daily_snapshots.

Usage:
  python aggregate.py [--date YYYY-MM-DD]
"""

import argparse
import logging
import os
import re
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
# because its descriptions are truncated to ~500 chars.
FULL_TEXT_SOURCES = ["jsearch", "greenhouse", "ashby", "lever"]

# Employer-board sources: authoritative, curated company boards re-scraped
# daily, so they carry a reliable last_seen_date for active-window filtering.
EMPLOYER_SOURCES = ["greenhouse", "ashby", "lever"]

# Feed sources: fetched once as new postings, not re-checked — filtered by
# posted_date rather than last_seen_date.
FEED_SOURCES = ["adzuna", "jsearch"]


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


COMPANY_ALIASES = {
    "jpmorganchase": "jpmorgan chase",
    "jp morgan chase": "jpmorgan chase",
    "jp morgan": "jpmorgan chase",
    "j.p. morgan": "jpmorgan chase",
    "j.p. morgan chase": "jpmorgan chase",
}


def count_companies(records: list[dict]) -> dict[str, int]:
    """Count PM job postings per company, deduplicated by dedup_hash.

    Employer-board postings (Greenhouse/Ashby/Lever) assign a unique dedup_hash
    per role-location, so multi-city roles still count each location separately.
    Feed sources (Adzuna/JSearch) re-fetch the same job across multiple runs;
    dedup_hash collapses those repeats to one, preventing artificial inflation.
    Falls back to raw_id when dedup_hash is absent.
    COMPANY_ALIASES merges known variant spellings that exist in the DB.
    """
    out: dict[str, set] = {}
    for r in records:
        company = r.get("company_normalized") or ""
        if not company:
            continue
        company = COMPANY_ALIASES.get(company, company)
        key = r.get("dedup_hash") or r.get("raw_id")
        out.setdefault(company, set()).add(key)
    return {company: len(ids) for company, ids in out.items()}


def fetch_active_pm_records(supabase: Client, since: date, version: str) -> list[dict]:
    """All US PM postings active within the last 7 days, across every source.

    Employer boards are re-scraped daily; a job is considered active if it was
    last confirmed in the window (last_seen_date >= since) OR was newly scraped
    in the window but not yet re-confirmed (last_seen_date IS NULL and
    posted_date >= since). The is_us filter is applied only to confirmed-active
    records because newly scraped records may not have is_us set yet.

    Feed sources (Adzuna, JSearch) are fetched once and never re-checked, so they
    are filtered by posted_date instead.
    """
    # Confirmed active: last_seen_date in window (is_us already reliable here)
    confirmed_board = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .gte("last_seen_date", str(since))
        .in_("source", EMPLOYER_SOURCES)
        .order("id")
    )
    # Newly scraped: last_seen_date NULL, posted in window
    new_board = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .is_("last_seen_date", "null")
        .gte("posted_date", str(since))
        .in_("source", EMPLOYER_SOURCES)
        .order("id")
    )
    feed_rows = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .gte("posted_date", str(since))
        .in_("source", FEED_SOURCES)
        .order("id")
    )
    seen_ids: set = set()
    raw_ids = []
    for r in confirmed_board + new_board + feed_rows:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            raw_ids.append(r["id"])
    if not raw_ids:
        return []
    return _batched_in(
        supabase,
        "job_postings_enriched",
        "raw_id,dedup_hash,company_normalized,has_ai_requirement,normalized_title",
        raw_ids,
        extra_eq=(("pipeline_version", version),),
    )


def compute_total_active_pm(supabase: Client, target_date: date, version: str) -> int:
    """Count distinct active PM openings across all sources as of target_date.

    Employer boards (Greenhouse/Ashby/Lever) are re-scraped daily, so a job is
    active if last_seen_date is within 7 days, or if it was newly scraped this
    week (last_seen_date IS NULL and posted_date within 7 days).

    Feeds (Adzuna/JSearch) are point-in-time; PM jobs posted within 30 days are
    assumed still open (typical PM posting duration).

    Results are restricted to PM-titled roles (normalized_title != 'Other') and
    deduplicated by dedup_hash so the same opening fetched from multiple sources
    is counted once.
    """
    board_since = str(target_date - timedelta(days=6))   # 7-day window
    feed_since  = str(target_date - timedelta(days=29))  # 30-day window

    confirmed_board = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .in_("source", EMPLOYER_SOURCES)
        .gte("last_seen_date", board_since)
        .order("id")
    )
    new_board = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .in_("source", EMPLOYER_SOURCES)
        .is_("last_seen_date", "null")
        .gte("posted_date", board_since)
        .order("id")
    )
    feed_rows = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .in_("source", FEED_SOURCES)
        .gte("posted_date", feed_since)
        .order("id")
    )

    all_ids = list({r["id"] for r in confirmed_board + new_board + feed_rows})
    if not all_ids:
        return 0

    enriched = _batched_in(
        supabase,
        "job_postings_enriched",
        "dedup_hash,normalized_title",
        all_ids,
        extra_eq=(("pipeline_version", version),),
    )
    return len({
        r["dedup_hash"]
        for r in enriched
        if r.get("dedup_hash") and r.get("normalized_title") != "Other"
    })


def fetch_all_full_text_enriched(supabase: Client, version: str) -> list[dict]:
    """Every enriched record from full-text sources, all-time (not one day).

    This is the corpus the AI Skills section is measured over: all PM postings
    we hold a complete description for, accumulated since tracking began.
    """
    raw_rows = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
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
        extra_eq=(("pipeline_version", version),),
    )


def fetch_domain_keywords(supabase: Client) -> dict[str, list[str]]:
    """Build the domain → keyword map from the ai_keywords table.

    This is the single source of truth for the AI taxonomy: enrich.py reads
    the same table to tag postings, so the domain grouping here can never
    drift from the keywords actually matched against job descriptions.
    """
    rows = (
        supabase.table("ai_keywords")
        .select("keyword,category")
        .eq("is_active", True)
        .execute()
        .data
    )
    out: dict[str, list[str]] = {}
    for r in rows:
        category = r.get("category")
        keyword = r.get("keyword")
        if category and keyword:
            out.setdefault(category, []).append(keyword)
    return out


def extract_quote_snippet(description: str, keywords: list[str], max_len: int = 240) -> Optional[str]:
    """Return the first sentence or bullet-point fragment in `description` that
    contains any of the keywords.

    Keywords are matched on word boundaries so short tokens like 'rag' do not
    spuriously match inside longer words (e.g. 'fragmented'). Over-long
    fragments are trimmed to a window around the keyword, snapped to word
    boundaries so the quote never starts or ends mid-word.
    """
    if not description:
        return None
    text = re.sub(r"\s+", " ", description).strip()
    # Stripped HTML can fuse a heading into the next sentence (e.g.
    # "AI PlatformThe Opportunity"); re-split lowercase→Uppercase-word joins.
    text = re.sub(r"([a-z])([A-Z][a-z])", r"\1 \2", text)
    # Split on sentence-enders and bullet markers — stripped-HTML descriptions
    # often join requirement bullets into one run-on line.
    fragments = re.split(r"(?<=[.!?])\s+|\s*[•·▪‣◦]\s*", text)
    patterns = [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in keywords]
    for frag in fragments:
        frag = frag.strip(" -–—•·\t")
        if len(frag) < 25:
            continue
        for pat in patterns:
            m = pat.search(frag)
            if not m:
                continue
            if len(frag) <= max_len:
                return frag
            # Trim a window around the keyword, then snap to word boundaries
            half = max_len // 2
            start = max(0, m.start() - half)
            end = min(len(frag), start + max_len)
            if start > 0:
                nxt = frag.find(" ", start)
                if 0 <= nxt < m.start():
                    start = nxt + 1
            if end < len(frag):
                prv = frag.rfind(" ", m.end(), end)
                if prv > 0:
                    end = prv
            snippet = frag[start:end].strip()
            return ("… " if start > 0 else "") + snippet + (" …" if end < len(frag) else "")
    return None


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

    # ── 1. VOLUME ────────────────────────────────────────────────────────────────
    # total_postings: distinct active PM openings across all sources, deduped by
    # (company, title). Employer boards use a 7-day last_seen_date window;
    # feeds use a 30-day posted_date window (typical PM job posting duration).
    # This replaces the old Adzuna raw count which over-counted by ~23x due to
    # broad keyword matching in job descriptions rather than titles.
    total_postings = compute_total_active_pm(supabase, target_date, PIPELINE_VERSION)
    log.info(f"total_active_pm_postings (all sources, deduped)={total_postings}")
    # new_postings_today: deduplicated count of jobs first ingested on
    # target_date across all sources (see new_jobs_on() in migration 004).
    new_jobs_resp = supabase.rpc(
        "new_jobs_on", {"day": str(target_date), "version": PIPELINE_VERSION}
    ).execute()
    new_postings_today = new_jobs_resp.data
    log.info(f"new_postings_today (deduped, all sources)={new_postings_today}")

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

    # ── 5. TOP 10 COMPANIES (ALL SOURCES) ────────────────────────────────────────
    # Count US PM openings active within the last 7 days across every source
    # (Adzuna, JSearch, Greenhouse, Ashby, Lever). Counted per raw_id — each
    # location-posting separately — and ranked by total PM openings. No AI
    # filtering: this section is purely about hiring volume.
    seven_day_start = target_date - timedelta(days=6)
    active_pm_records = [
        r for r in fetch_active_pm_records(supabase, seven_day_start, PIPELINE_VERSION)
        if r.get("normalized_title") != "Other"
    ]
    log.info(f"Active PM records after title filter: {len(active_pm_records)}")

    # Direction: compare against the snapshot from exactly 7 days ago.
    prev_week_date = target_date - timedelta(days=7)
    prev_snap_resp = (
        supabase.table("daily_snapshots")
        .select("top_employers_ai_skills")
        .eq("snapshot_date", str(prev_week_date))
        .execute()
    )
    prev_totals: dict[str, int] = {}
    if prev_snap_resp.data:
        prev_data = prev_snap_resp.data[0].get("top_employers_ai_skills") or {}
        for c in prev_data.get("companies") or []:
            prev_totals[c["company"]] = c.get("total_count", 0)

    current_total = count_companies(active_pm_records)
    top_10_companies = sorted(current_total.items(), key=lambda x: x[1], reverse=True)[:10]

    # Snapshot key kept as top_employers_ai_skills for backward compatibility.
    top_employers_ai_skills = {
        "window_days": 7,
        "window_end": str(target_date),
        "total_active_pm": len(active_pm_records),
        "companies": [
            {
                "rank": i + 1,
                "company": company,
                "total_count": total_count,
                "prev_total_count": prev_totals.get(company, 0),
                "direction": company_direction(total_count, prev_totals.get(company, 0)),
            }
            for i, (company, total_count) in enumerate(top_10_companies)
        ],
    }
    log.info(f"Top companies: {len(active_pm_records)} active PM postings across all sources")

    # ── 5b. AI SKILLS BY DOMAIN ──────────────────────────────────────────────────
    # Measured over every PM posting we hold a full description for — all
    # full-text sources (JSearch, Greenhouse, Ashby, Lever), accumulated since
    # tracking began, deduplicated by dedup_hash. For each domain, count
    # distinct postings mentioning its keywords; attach one representative
    # quote, spread across companies where the data allows.
    all_ft = fetch_all_full_text_enriched(supabase, PIPELINE_VERSION)
    ft_by_hash: dict[str, dict] = {}
    for r in all_ft:
        h = r.get("dedup_hash")
        if h and h not in ft_by_hash:
            ft_by_hash[h] = r
    ft_distinct = list(ft_by_hash.values())
    ft_total = len(ft_distinct)
    ft_ai = [r for r in ft_distinct if r.get("has_ai_requirement")]
    ft_ai_rate = round(len(ft_ai) / ft_total * 100, 1) if ft_total else None

    domain_keywords = fetch_domain_keywords(supabase)
    domain_matches: dict[str, list] = {}
    domain_counts: dict[str, int] = {}
    for slug, keywords in domain_keywords.items():
        kw_set = set(keywords)
        matching = [
            r for r in ft_ai
            if kw_set & set(r.get("ai_keyword_matches") or [])
        ]
        domain_matches[slug] = matching
        domain_counts[slug] = len(matching)

    # Pick one sample posting per domain for its quote. Process the most
    # constrained domains (fewest matching postings) first, and prefer a
    # posting from a company not yet quoted — so the cards spread across
    # companies for visual variety where the data allows.
    domain_sample_ids: dict[str, int] = {}
    used_raw_ids: set = set()
    used_companies: set = set()
    for slug in sorted(domain_matches, key=lambda s: domain_counts[s]):
        matching = domain_matches[slug]
        if not matching:
            continue
        pick = (
            next((r for r in matching
                  if (r.get("company_normalized") or "") not in used_companies), None)
            or next((r for r in matching if r["raw_id"] not in used_raw_ids), None)
            or matching[0]
        )
        domain_sample_ids[slug] = pick["raw_id"]
        used_raw_ids.add(pick["raw_id"])
        company = pick.get("company_normalized") or ""
        if company:
            used_companies.add(company)

    # Batch-fetch description_text + company for one sample posting per domain
    all_sample_raw_ids = list(set(domain_sample_ids.values()))
    desc_by_raw_id: dict[int, dict] = {}
    if all_sample_raw_ids:
        raw_rows = _batched_in(
            supabase, "job_postings_raw", "id,company,description_text", all_sample_raw_ids
        )
        for row in raw_rows:
            desc_by_raw_id[row["id"]] = row

    domain_items = []
    for slug, keywords in domain_keywords.items():
        raw_id = domain_sample_ids.get(slug)
        raw = desc_by_raw_id.get(raw_id) if raw_id else None
        domain_items.append({
            "slug":    slug,
            "count":   domain_counts.get(slug, 0),
            "quote":   extract_quote_snippet(raw.get("description_text") or "", keywords) if raw else None,
            "company": (raw.get("company") or None) if raw else None,
        })
    domain_items.sort(key=lambda d: d["count"], reverse=True)

    top_ai_skills["domains"] = domain_items
    top_ai_skills["full_text_total"] = ft_total
    top_ai_skills["full_text_ai_total"] = len(ft_ai)
    top_ai_skills["full_text_ai_rate"] = ft_ai_rate

    # Top companies by AI-requiring PM openings — same active 7-day window as
    # Section II, filtered to postings where has_ai_requirement is True.
    ai_active_records = [r for r in active_pm_records if r.get("has_ai_requirement")]
    ai_active_counts = count_companies(ai_active_records)
    top_10_ai_companies = sorted(
        ai_active_counts.items(), key=lambda x: x[1], reverse=True
    )[:10]
    top_ai_skills["top_ai_employers"] = [
        {"rank": i + 1, "company": company, "count": count}
        for i, (company, count) in enumerate(top_10_ai_companies)
    ]
    top_ai_skills["top_ai_employers_window_end"] = str(target_date)
    log.info(
        f"AI skills: {ft_total} full-text postings, {len(ft_ai)} require AI "
        f"({ft_ai_rate}%); {sum(1 for d in domain_items if d['count'] > 0)}/{len(domain_items)} domains with signal"
    )

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
