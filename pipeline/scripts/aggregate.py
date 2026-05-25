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

# All sources we currently use. Every source here returns a complete job
# description (no truncation), so the active-openings population is also the
# AI-analysis population — no separate "sample" concept. Adzuna was removed in
# favor of full-text-only sourcing.
EMPLOYER_SOURCES = ["greenhouse", "ashby", "lever"]   # curated boards, re-scraped daily
FEED_SOURCES     = ["jsearch"]                         # commercial feed, point-in-time
FULL_TEXT_SOURCES = EMPLOYER_SOURCES + FEED_SOURCES    # alias kept for clarity in callers
ALL_SOURCES       = FULL_TEXT_SOURCES                  # everything we count


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


def fetch_active_pm_records(supabase: Client, target_date: date, version: str) -> list[dict]:
    """All US PM postings active as of target_date, across every source.

    Uses the same windowing as compute_total_active_pm so Sections II and IV
    sum to the same 'active' population as Section I (total_postings):
    - Employer boards (Greenhouse/Ashby/Lever): 7-day last_seen_date window
      OR last_seen_date IS NULL with posted_date in the same window (newly
      scraped, not yet re-confirmed).
    - Feed sources (JSearch): 45-day posted_date window — these are point-in-
      time fetches with no re-verification, so we assume a posting remains
      open for up to 45 days from posted_date. PM-specific posting lifetimes
      (senior / AI-PM roles) often run past the generic 30-day rule of thumb,
      so 45 gives better coverage without leaning on stale data.
    """
    board_since = str(target_date - timedelta(days=6))    # 7-day boards window
    feed_since  = str(target_date - timedelta(days=44))   # 45-day feeds window

    # Confirmed active: last_seen_date within board window
    confirmed_board = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .gte("last_seen_date", board_since)
        .in_("source", EMPLOYER_SOURCES)
        .order("id")
    )
    # Newly scraped: last_seen_date NULL, posted in board window
    new_board = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .is_("last_seen_date", "null")
        .gte("posted_date", board_since)
        .in_("source", EMPLOYER_SOURCES)
        .order("id")
    )
    feed_rows = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .gte("posted_date", feed_since)
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


def compute_new_pm_postings_today(supabase: Client, target_date: date, version: str) -> int:
    """Count distinct PM jobs first ingested on target_date (never seen before).

    Replaces the all-titles new_jobs_on() RPC, which counted every job record
    regardless of title. This function:
    - Filters to PM-titled roles (normalized_title != 'Other')
    - Deduplicates by dedup_hash (cross-source duplicates count once)
    - Excludes hashes already seen on earlier run_dates (truly new only)
    """
    today_raw = fetch_all_rows(
        lambda: supabase.table("job_postings_raw")
        .select("id")
        .eq("run_date", str(target_date))
        .order("id")
    )
    if not today_raw:
        return 0

    today_enriched = _batched_in(
        supabase, "job_postings_enriched",
        "raw_id,dedup_hash,normalized_title",
        [r["id"] for r in today_raw],
        extra_eq=(("pipeline_version", version),),
    )
    today_pm_hashes = {
        r["dedup_hash"]
        for r in today_enriched
        if r.get("dedup_hash") and r.get("normalized_title") != "Other"
    }
    if not today_pm_hashes:
        return 0

    # For each today-PM hash, collect all raw_ids ever enriched with that hash,
    # then check whether any of those raw records have run_date before today.
    hash_by_raw_id: dict = {}
    hash_list = list(today_pm_hashes)
    for i in range(0, len(hash_list), 50):
        batch = hash_list[i:i + 50]
        offset = 0
        while True:
            resp = (
                supabase.table("job_postings_enriched")
                .select("raw_id,dedup_hash")
                .eq("pipeline_version", version)
                .in_("dedup_hash", batch)
                .range(offset, offset + 999)
                .execute()
            )
            for r in resp.data:
                hash_by_raw_id[r["raw_id"]] = r["dedup_hash"]
            if len(resp.data) < 1000:
                break
            offset += 1000

    hashes_seen_before: set = set()
    raw_id_list = list(hash_by_raw_id.keys())
    for i in range(0, len(raw_id_list), 100):
        batch = raw_id_list[i:i + 100]
        resp = (
            supabase.table("job_postings_raw")
            .select("id")
            .lt("run_date", str(target_date))
            .in_("id", batch)
            .execute()
        )
        for r in resp.data:
            h = hash_by_raw_id.get(r["id"])
            if h:
                hashes_seen_before.add(h)

    return len(today_pm_hashes - hashes_seen_before)


def compute_total_active_pm(supabase: Client, target_date: date, version: str) -> tuple[int, int]:
    """Count active PM openings as of target_date, and how many require AI.

    Returns (total_active, total_active_with_ai).

    Employer boards (Greenhouse/Ashby/Lever) are re-scraped daily, so a job is
    active if last_seen_date is within 7 days, or if it was newly scraped this
    week (last_seen_date IS NULL and posted_date within 7 days).

    JSearch is point-in-time with no re-verification; PM jobs posted within 45
    days are assumed still open (PM-role posting lifetimes — especially senior
    and AI-leaning roles — often run past the generic 30-day rule of thumb).

    All sources here return complete job descriptions, so every active posting
    is eligible for AI-keyword analysis. Results are restricted to PM-titled
    roles (normalized_title != 'Other') and deduplicated by dedup_hash so the
    same opening fetched from multiple sources is counted once.
    """
    board_since = str(target_date - timedelta(days=6))   # 7-day window
    feed_since  = str(target_date - timedelta(days=44))  # 45-day window

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
        return (0, 0)

    enriched = _batched_in(
        supabase,
        "job_postings_enriched",
        "dedup_hash,normalized_title,has_ai_requirement",
        all_ids,
        extra_eq=(("pipeline_version", version),),
    )
    pm = [r for r in enriched if r.get("dedup_hash") and r.get("normalized_title") != "Other"]
    total_hashes = {r["dedup_hash"] for r in pm}
    ai_hashes = {r["dedup_hash"] for r in pm if r.get("has_ai_requirement")}
    return (len(total_hashes), len(ai_hashes))


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
    # Also split when an ALLCAPS heading (e.g. "ROLE OVERVIEW") runs straight
    # into a normal sentence (e.g. "As a Staff Engineer…").
    text = re.sub(r"([A-Z]{3,})\s+([A-Z][a-z])", r"\1. \2", text)
    # Split on sentence-enders and bullet markers — stripped-HTML descriptions
    # often join requirement bullets into one run-on line.
    fragments = re.split(r"(?<=[.!?])\s+|\s*[•·▪‣◦]\s*", text)
    patterns = [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in keywords]
    # Patterns that look like leftover headings: lines that are mostly ALLCAPS,
    # or start with one. We want quotes that read like prose, not bleed-through
    # from HTML labels. We also skip "About <Company>" boilerplate openings.
    HEADING_RE = re.compile(r"^[A-Z][A-Z &/\-]{2,}(?:\s|$)")
    BOILERPLATE_RE = re.compile(r"^(?:about\s+\w|the\s+role|role\s+overview|the\s+opportunity)", re.IGNORECASE)

    def looks_like_heading(s: str) -> bool:
        if HEADING_RE.match(s):
            return True
        if BOILERPLATE_RE.match(s):
            return True
        # Mostly uppercase letters at the start (heading bleed)
        head = s[:30]
        upper = sum(1 for c in head if c.isupper())
        lower = sum(1 for c in head if c.islower())
        return upper > 6 and upper > lower * 2

    for frag in fragments:
        frag = frag.strip(" -–—•·\t")
        if len(frag) < 25:
            continue
        if looks_like_heading(frag):
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
    EXPECTED_SOURCES = ["jsearch", "greenhouse", "ashby"]
    logs_resp = (
        supabase.table("fetch_log")
        .select("*")
        .eq("run_date", str(target_date))
        .in_("source", EXPECTED_SOURCES)
        .execute()
    )
    logs_by_source = {row["source"]: row for row in logs_resp.data}
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

    # ── 1. VOLUME + AI RATE ────────────────────────────────────────────────────
    # total_postings: distinct active PM openings across all sources, deduped by
    # (company, title). Employer boards use a 7-day last_seen_date window;
    # JSearch uses a 45-day posted_date window. All sources here return full
    # job descriptions, so every active opening is also AI-eligible and the
    # AI rate is computed over the same population.
    total_postings, total_postings_ai = compute_total_active_pm(supabase, target_date, PIPELINE_VERSION)
    log.info(
        f"total_active_pm_postings={total_postings}  "
        f"requiring_ai={total_postings_ai}"
    )
    ai_penetration_rate = (
        round(total_postings_ai / total_postings * 100, 2)
        if total_postings > 0 else None
    )
    log.info(
        f"AI penetration over active openings: "
        f"{total_postings_ai}/{total_postings} = {ai_penetration_rate}%"
    )

    # new_postings_today: distinct PM jobs first seen today across all sources,
    # deduped by dedup_hash. PM-titled only (normalized_title != 'Other').
    new_postings_today = compute_new_pm_postings_today(supabase, target_date, PIPELINE_VERSION)
    log.info(f"new_pm_postings_today (PM-only, deduped)={new_postings_today}")

    # ── 2. ROLLING AVERAGES ───────────────────────────────────────────────────────
    total_postings_7day_avg = rolling_7day_avg(supabase, "total_postings", target_date)
    new_postings_7day_avg = rolling_7day_avg(supabase, "new_postings_today", target_date)
    ai_penetration_7day_avg = rolling_7day_avg(supabase, "ai_penetration_rate", target_date)

    # ── 3. TODAY-ONLY AI SNAPSHOT (used only inside top_ai_skills below) ─────────
    # Kept narrow because Section III intro counts come from the all-time
    # full-text corpus, not from today's slice.
    todays_full_text = fetch_enriched_full_text(supabase, target_date)
    distinct_hashes = {r["dedup_hash"] for r in todays_full_text if r.get("dedup_hash")}
    ai_hashes = {
        r["dedup_hash"]
        for r in todays_full_text
        if r.get("has_ai_requirement") and r.get("dedup_hash")
    }
    total_today = len(distinct_hashes)
    ai_today = len(ai_hashes)

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
        "total_ai_postings_today": ai_today,  # deduped by dedup_hash, full-text only
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

    # ── 5. TOP COMPANIES (UNIFIED: TOTAL + AI) ───────────────────────────────────
    # One ranked list, joined with the AI cut. For each top-N company we expose:
    #   total_count    — active PM openings
    #   ai_count       — of those, how many require AI
    #   ai_rate        — ai_count / total_count, rounded
    #   postings       — drill-down list of the underlying openings
    # Ranked by total_count (volume), since that's what answers "where are PMs
    # being hired" — AI columns are an additional lens, not the ranking signal.
    active_pm_records = [
        r for r in fetch_active_pm_records(supabase, target_date, PIPELINE_VERSION)
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

    # Bucket records by company, deduped by dedup_hash, AI-flagged subset, and
    # the raw_ids backing each bucket (used to look up drill-down details).
    # Also track per-raw-id AI flag so the drill-down can mark individual postings.
    by_company: dict[str, dict] = {}
    raw_id_is_ai: dict = {}
    for r in active_pm_records:
        comp = r.get("company_normalized") or ""
        if not comp:
            continue
        comp = COMPANY_ALIASES.get(comp, comp)
        bucket = by_company.setdefault(comp, {"hashes": set(), "ai_hashes": set(), "raw_ids": set()})
        h = r.get("dedup_hash")
        if h:
            bucket["hashes"].add(h)
            if r.get("has_ai_requirement"):
                bucket["ai_hashes"].add(h)
        rid = r.get("raw_id")
        if rid:
            bucket["raw_ids"].add(rid)
            if r.get("has_ai_requirement"):
                raw_id_is_ai[rid] = True

    company_rows = [
        {
            "company": comp,
            "total": len(b["hashes"]),
            "ai":    len(b["ai_hashes"]),
            "raw_ids": b["raw_ids"],
        }
        for comp, b in by_company.items()
    ]
    company_rows.sort(key=lambda c: (-c["total"], c["company"]))
    top_companies_combined = company_rows[:10]

    # Fetch drill-down details (title, location, posted_date, source) for the
    # raw_ids in the top-N buckets only. We embed up to 12 postings per company
    # to keep the JSONB blob small but still useful.
    top_raw_ids = [rid for row in top_companies_combined for rid in row["raw_ids"]]
    raw_detail_map: dict = {}
    if top_raw_ids:
        for i in range(0, len(top_raw_ids), 100):
            batch = list(top_raw_ids)[i:i + 100]
            resp = (
                supabase.table("job_postings_raw")
                .select("id,title,location,posted_date,source,source_id,url")
                .in_("id", batch)
                .execute()
            )
            for row in resp.data:
                raw_detail_map[row["id"]] = row

    top_employers_ai_skills = {
        "window_end": str(target_date),
        "total_active_pm": total_postings,
        "total_active_pm_ai": total_postings_ai,
        "companies": [
            {
                "rank":        i + 1,
                "company":     row["company"],
                "total_count": row["total"],
                "ai_count":    row["ai"],
                "ai_rate":     round(row["ai"] / row["total"] * 100, 1) if row["total"] else 0.0,
                "prev_total_count": prev_totals.get(row["company"], 0),
                "direction":   company_direction(row["total"], prev_totals.get(row["company"], 0)),
                "postings":    sorted(
                    [
                        {
                            "title":       raw_detail_map[rid].get("title"),
                            "location":    raw_detail_map[rid].get("location"),
                            "posted_date": raw_detail_map[rid].get("posted_date"),
                            "source":      raw_detail_map[rid].get("source"),
                            "url":         raw_detail_map[rid].get("url"),
                            "has_ai":      bool(raw_id_is_ai.get(rid, False)),
                        }
                        for rid in row["raw_ids"] if rid in raw_detail_map
                    ],
                    key=lambda p: (
                        1 if p.get("has_ai") else 0,
                        p.get("posted_date") or "",
                        p.get("title") or "",
                    ),
                    reverse=True,
                )[:12],
            }
            for i, row in enumerate(top_companies_combined)
        ],
    }
    log.info(
        f"Top companies (combined): top10 totals "
        f"{[(c['company'], c['total_count'], c['ai_count']) for c in top_employers_ai_skills['companies']]}"
    )

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
            supabase, "job_postings_raw", "id,company,title,url,description_text", all_sample_raw_ids
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
            "title":   (raw.get("title") or None) if raw else None,
            "url":     (raw.get("url") or None) if raw else None,
        })
    domain_items.sort(key=lambda d: d["count"], reverse=True)

    top_ai_skills["domains"] = domain_items
    # Active-population denominators for the domain cards. All-time corpus
    # totals are still emitted (full_text_*) for backward compatibility with
    # historical snapshots that referenced them.
    top_ai_skills["active_total"] = total_postings
    top_ai_skills["active_ai_total"] = total_postings_ai
    top_ai_skills["active_ai_rate"] = ai_penetration_rate
    top_ai_skills["full_text_total"] = ft_total
    top_ai_skills["full_text_ai_total"] = len(ft_ai)
    top_ai_skills["full_text_ai_rate"] = ft_ai_rate
    log.info(
        f"AI skills: {ft_total} full-text postings (all-time), {len(ft_ai)} require AI "
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
