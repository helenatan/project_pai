"""
enrich.py -- Read unprocessed raw records, apply enrichment logic, write to job_postings_enriched.

Usage:
  python enrich.py --version v1.0 [--since YYYY-MM-DD] [--force-reprocess]
"""

import argparse
import hashlib
import logging
import os
import re
import sys
from typing import Optional

from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

TITLE_PATTERNS = [
    # Order matters: more specific patterns before less specific
    ("CPO",       ["chief product officer", "cpo"]),
    ("VP",        ["vp of product", "vice president of product", "vp product", "head of product"]),
    ("Director",  ["director of product", "director product", "group product manager", "gpm"]),
    ("Staff PM",  ["staff product manager", "principal product manager"]),
    ("Senior PM", ["senior product manager", "sr. product manager", "sr product manager", "product manager iii"]),
    ("APM",       ["associate product manager", "junior product manager", "apm"]),
    ("PM",        ["product manager", " pm ", "product manager i", "product manager ii"]),
]

SENIORITY_MAP = {
    "APM": "junior",
    "PM": "mid",
    "Senior PM": "senior",
    "Staff PM": "staff",
    "Director": "director",
    "VP": "vp",
    "CPO": "vp",
}


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


def normalize_title(raw_title: str) -> tuple[str, str]:
    """Return (normalized_title, seniority_level)."""
    if not raw_title:
        return "Other", "unknown"
    title_lower = raw_title.lower().strip()
    for normalized, patterns in TITLE_PATTERNS:
        for pattern in patterns:
            if pattern in title_lower:
                return normalized, SENIORITY_MAP[normalized]
    return "Other", "unknown"


def normalize_company_name(raw_name: str) -> str:
    if not raw_name:
        return ""
    name = raw_name.lower().strip()
    for suffix in [
        ", inc.", ", inc", ", llc", ", llc.", ", ltd", ", ltd.",
        ", corp.", ", corp", ", co.", " inc.", " inc", " llc", " ltd",
    ]:
        name = name.replace(suffix, "")
    return " ".join(name.split())


def compute_dedup_hash(company: str, title: str) -> str:
    company_norm = normalize_company_name(company)
    title_norm = (title or "").lower().strip()
    dedup_input = f"{company_norm}|{title_norm}"
    return hashlib.md5(dedup_input.encode()).hexdigest()


def fetch_active_keywords(supabase: Client) -> list[str]:
    resp = (
        supabase.table("ai_keywords")
        .select("keyword")
        .eq("is_active", True)
        .execute()
    )
    return [row["keyword"] for row in resp.data]


def match_keywords(description_text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    text = (description_text or "").lower()
    matches = [
        kw for kw in keywords
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text)
    ]
    return len(matches) > 0, matches


def fetch_unprocessed(supabase: Client, version: str, since: Optional[str]) -> list[dict]:
    """Return raw records that have no enriched row for this version."""
    def _raw_query():
        q = supabase.table("job_postings_raw").select(
            "id, title, company, description_text, posted_date"
        )
        if since:
            q = q.gte("posted_date", since)
        return q.order("id")

    raw_rows = fetch_all_rows(_raw_query)

    if not raw_rows:
        return []

    raw_ids = [r["id"] for r in raw_rows]

    # Batch the .in_() lookup to avoid URL length limits (max ~100 IDs per request)
    already_enriched: set = set()
    batch_size = 100
    for i in range(0, len(raw_ids), batch_size):
        batch = raw_ids[i : i + batch_size]
        enriched_resp = (
            supabase.table("job_postings_enriched")
            .select("raw_id")
            .eq("pipeline_version", version)
            .in_("raw_id", batch)
            .execute()
        )
        already_enriched.update(row["raw_id"] for row in enriched_resp.data)

    return [r for r in raw_rows if r["id"] not in already_enriched]


def fetch_all_for_version(supabase: Client, version: str, since: Optional[str]) -> list[dict]:
    """Return all raw records within date range (for --force-reprocess)."""
    def _raw_query():
        q = supabase.table("job_postings_raw").select(
            "id, title, company, description_text, posted_date"
        )
        if since:
            q = q.gte("posted_date", since)
        return q.order("id")

    return fetch_all_rows(_raw_query)


def enrich_record(raw: dict, keywords: list[str], version: str) -> dict:
    normalized_title, seniority_level = normalize_title(raw.get("title"))
    company_normalized = normalize_company_name(raw.get("company") or "")
    dedup_hash = compute_dedup_hash(raw.get("company") or "", raw.get("title") or "")
    has_ai, ai_matches = match_keywords(raw.get("description_text") or "", keywords)

    return {
        "raw_id": raw["id"],
        "pipeline_version": version,
        "dedup_hash": dedup_hash,
        "company_normalized": company_normalized,
        "normalized_title": normalized_title,
        "seniority_level": seniority_level,
        "has_ai_requirement": has_ai,
        "ai_keyword_matches": ai_matches,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v1.0")
    parser.add_argument("--since", default=None)
    parser.add_argument("--force-reprocess", action="store_true")
    args = parser.parse_args()

    log.info(f"Starting enrichment: version={args.version} since={args.since} force={args.force_reprocess}")

    supabase = get_supabase()
    keywords = fetch_active_keywords(supabase)
    log.info(f"Loaded {len(keywords)} active AI keywords")

    if args.force_reprocess:
        raw_records = fetch_all_for_version(supabase, args.version, args.since)
    else:
        raw_records = fetch_unprocessed(supabase, args.version, args.since)

    log.info(f"Records to enrich: {len(raw_records)}")

    inserted = 0
    skipped = 0
    errors = 0

    for raw in raw_records:
        try:
            enriched = enrich_record(raw, keywords, args.version)
            if args.force_reprocess:
                supabase.table("job_postings_enriched").upsert(
                    enriched, on_conflict="raw_id,pipeline_version"
                ).execute()
            else:
                supabase.table("job_postings_enriched").insert(
                    enriched
                ).execute()
            inserted += 1
        except Exception as e:
            log.error(f"Failed to enrich raw_id={raw['id']}: {e}")
            errors += 1

    log.info(f"Enrichment complete: inserted={inserted} skipped={skipped} errors={errors}")

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
