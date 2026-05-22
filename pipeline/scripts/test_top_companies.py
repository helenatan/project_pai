"""
test_top_companies.py -- Data quality check for the top 10 PM companies.

Cross-references the latest snapshot's top_employers_ai_skills against each
company's live career-site/ATS to validate PM opening counts and surface
discrepancies.

Why pipeline count != ATS count (always expected):
  - Pipeline deduplicates by MD5(company_normalized|title_lower), so multiple
    openings with identical titles count as 1 in the pipeline.
  - Pipeline only counts jobs first-seen within the 7-day rolling window.
  - ATS reflects all currently-active open roles today.
  Therefore: ATS live count >= pipeline 7-day count is the normal baseline.

Discrepancy classifications:
  ok          ATS >= pipeline; delta is within expected structural differences.
  ok_stale    Pipeline slightly > ATS; recent roles closed within the window.
  warning     Pipeline >> ATS or ATS >> pipeline at unusual magnitudes.
  uncurated   Company not in employer_boards.csv (count from Adzuna/JSearch only).
  ats_error   ATS fetch failed (wrong slug, dead endpoint, network issue) -- bug.

Exit codes:
  0  All checks pass (ok, ok_stale, uncurated, warning are non-blocking).
  1  One or more ats_error results (config/connectivity bug requiring a fix).

Usage:
  python test_top_companies.py [--date YYYY-MM-DD]
"""

import argparse
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from supabase import create_client, Client

# Re-use shared helpers so title filtering is identical to the live pipeline.
_SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS))
from fetch_employers import (
    fetch_ashby_board,
    fetch_greenhouse_board,
    is_pm_title,
    load_boards,
)
from enrich import normalize_company_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# ATS count > this multiple of pipeline count → unusual under-count in pipeline.
RATIO_WARN_THRESHOLD = 8
# Pipeline count exceeds ATS count by more than this → investigate stale data.
STALE_WARN_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def build_boards_lookup(boards: list[dict]) -> dict[str, dict]:
    """Map normalize_company_name(company) → board row."""
    return {normalize_company_name(b["company"]): b for b in boards}


def fetch_live_pm_count(
    session: requests.Session, ats: str, slug: str
) -> tuple[int, list[str]]:
    """
    Return (pm_job_count, sample_titles) from the live ATS.
    Uses the same is_pm_title filter as fetch_employers.py.
    """
    if ats == "greenhouse":
        jobs = fetch_greenhouse_board(session, slug)
    elif ats == "ashby":
        jobs = fetch_ashby_board(session, slug)
    else:
        raise ValueError(f"Unknown ATS: {ats}")

    pm_jobs = [j for j in jobs if is_pm_title(j.get("title", ""))]
    sample = [j.get("title", "") for j in pm_jobs[:4]]
    return len(pm_jobs), sample


# ---------------------------------------------------------------------------
# Discrepancy classification
# ---------------------------------------------------------------------------

def classify(pipeline_count: int, ats_count: int) -> tuple[str, str]:
    """
    Return (status, explanation).

    The structural expectation is ats_count >= pipeline_count because:
      1. Pipeline deduplicates by (company, title): N postings with the same
         title = 1 pipeline unit.
      2. Pipeline window is 7 days; ATS shows all currently-open roles.
    """
    delta = ats_count - pipeline_count  # positive = ATS has more (expected)

    if ats_count == 0 and pipeline_count == 0:
        return "ok", "Both ATS and pipeline show 0 PM openings."

    if ats_count == 0 and pipeline_count > 0:
        return "warning", (
            f"ATS shows 0 active PM roles but pipeline counted {pipeline_count} in the "
            "7-day window. Likely cause: all roles closed/filled since first ingestion. "
            "If this persists tomorrow, check that the ATS slug is correct."
        )

    if pipeline_count > ats_count + STALE_WARN_THRESHOLD:
        return "warning", (
            f"Pipeline ({pipeline_count}) exceeds live ATS ({ats_count}) by "
            f"{pipeline_count - ats_count}. Roles accumulated over the 7-day window "
            "but have since been filled or removed from the ATS. Normal after a hiring "
            f"surge; investigate if this exceeds {STALE_WARN_THRESHOLD} consistently."
        )

    if pipeline_count > ats_count:
        return "ok_stale", (
            f"Pipeline ({pipeline_count}) slightly exceeds ATS ({ats_count}) by "
            f"{pipeline_count - ats_count}. Roles ingested earlier in the 7-day "
            "window have since closed — expected churn."
        )

    if ats_count > pipeline_count * RATIO_WARN_THRESHOLD and pipeline_count > 0:
        ratio = ats_count / pipeline_count
        return "warning", (
            f"ATS ({ats_count}) is {ratio:.1f}× the pipeline count ({pipeline_count}). "
            "Pipeline may be under-counting. Check whether: (a) many distinct PM titles "
            "exist that pass is_pm_title but share a deduplicated title string, or (b) "
            "roles were mostly posted before the 7-day window opened."
        )

    # ats_count >= pipeline_count and ratio is reasonable
    if delta == 0:
        return "ok", "ATS and pipeline counts match exactly."
    return "ok", (
        f"ATS has {delta} more opening(s) than pipeline — expected: multiple openings "
        "with the same title collapse to 1 in the pipeline (dedup by title)."
    )


# ---------------------------------------------------------------------------
# Per-company check
# ---------------------------------------------------------------------------

def check_company(
    rank: int,
    company_name: str,
    pipeline_count: int,
    ai_count: int,
    boards_lookup: dict[str, dict],
    session: requests.Session,
) -> dict:
    result = {
        "rank": rank,
        "company": company_name,
        "pipeline_count": pipeline_count,
        "pipeline_ai_count": ai_count,
        "ats": None,
        "slug": None,
        "ats_count": None,
        "sample_titles": [],
        "status": None,
        "explanation": None,
    }

    norm = normalize_company_name(company_name)
    board = boards_lookup.get(norm)

    if board is None:
        result["status"] = "uncurated"
        result["explanation"] = (
            "Not found in employer_boards.csv. This company's count comes exclusively "
            "from Adzuna/JSearch public APIs — no direct ATS cross-check is possible. "
            "If it appears in the top 10 consistently, consider adding it to the "
            "curated list."
        )
        return result

    result["ats"] = board["ats"]
    result["slug"] = board["slug"]

    try:
        time.sleep(0.5)  # polite pacing, same as fetch_employers.py
        ats_count, sample_titles = fetch_live_pm_count(session, board["ats"], board["slug"])
        result["ats_count"] = ats_count
        result["sample_titles"] = sample_titles
        status, explanation = classify(pipeline_count, ats_count)
        result["status"] = status
        result["explanation"] = explanation
    except Exception as e:
        result["status"] = "ats_error"
        result["explanation"] = (
            f"ATS fetch failed: {e}. "
            "Check that the slug in employer_boards.csv is still correct and that "
            f"the {board['ats']} API is reachable."
        )
        log.error(f"  {company_name} ({board['slug']}): {e}")

    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

STATUS_ICONS = {
    "ok": "✓",
    "ok_stale": "~",
    "uncurated": "?",
    "warning": "!",
    "ats_error": "✗",
}


def print_report(results: list[dict], snapshot_date: str) -> None:
    print()
    print(f"=== Top 10 PM Companies — QA Check (snapshot: {snapshot_date}) ===")
    print()

    col_w = {"company": 22, "ats": 8, "slug": 18, "pipeline": 12, "live": 8, "delta": 6}
    hdr = (
        f"  {'':1} {'#':>3}  "
        f"{'Company':<{col_w['company']}} "
        f"{'ATS':<{col_w['ats']}} "
        f"{'Slug':<{col_w['slug']}} "
        f"{'Pipeline(7d)':>{col_w['pipeline']}} "
        f"{'ATS Live':>{col_w['live']}} "
        f"{'Δ':>{col_w['delta']}}"
    )
    print(hdr)
    print("  " + "─" * (len(hdr) - 2))

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        icon = STATUS_ICONS.get(r["status"], "?")
        ats_live = str(r["ats_count"]) if r["ats_count"] is not None else "—"
        delta_str = (
            f"{r['ats_count'] - r['pipeline_count']:+d}"
            if r["ats_count"] is not None
            else "—"
        )
        ats_name = r["ats"] or "—"
        slug = r["slug"] or "—"
        print(
            f"  {icon} {r['rank']:>3}  "
            f"{r['company']:<{col_w['company']}} "
            f"{ats_name:<{col_w['ats']}} "
            f"{slug:<{col_w['slug']}} "
            f"{r['pipeline_count']:>{col_w['pipeline']}} "
            f"{ats_live:>{col_w['live']}} "
            f"{delta_str:>{col_w['delta']}}"
        )
        if r["status"] not in ("ok",):
            print(f"          └─ {r['explanation']}")
        if r.get("sample_titles"):
            titles = "; ".join(f'"{t}"' for t in r["sample_titles"])
            print(f"          └─ ATS sample: {titles}")

    print()
    summary_parts = [
        f"{count} {status}" for status, count in sorted(status_counts.items())
    ]
    print(f"  Summary: {', '.join(summary_parts)}")
    print()

    # Legend
    print("  Legend:")
    for code, icon in STATUS_ICONS.items():
        desc = {
            "ok": "counts reconcile within expected structural differences",
            "ok_stale": "pipeline slightly > ATS; roles closed within the window",
            "uncurated": "not in employer_boards.csv; Adzuna/JSearch only",
            "warning": "unexpected discrepancy — review explanation",
            "ats_error": "ATS fetch failed — potential config bug",
        }[code]
        print(f"    {icon}  {code:<12} {desc}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        default=None,
        help="Snapshot date YYYY-MM-DD (default: yesterday, matching aggregate.py)",
    )
    args = parser.parse_args()

    target_date = (
        date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)
    )

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    resp = (
        supabase.table("daily_snapshots")
        .select("snapshot_date,top_employers_ai_skills")
        .eq("snapshot_date", str(target_date))
        .execute()
    )
    if not resp.data:
        log.error(f"No snapshot found for {target_date}. Run aggregate.py first.")
        sys.exit(1)

    employers_data = resp.data[0].get("top_employers_ai_skills") or {}
    companies = employers_data.get("companies", [])
    if not companies:
        log.error(f"top_employers_ai_skills is empty for {target_date}.")
        sys.exit(1)

    log.info(f"Checking {len(companies)} companies from snapshot {target_date}")

    boards_lookup = build_boards_lookup(load_boards())
    session = requests.Session()

    results = []
    for entry in companies:
        company = entry["company"]
        pipeline_count = entry["total_count"]
        ai_count = entry.get("ai_count", 0)
        log.info(f"  #{entry['rank']} {company}: pipeline_count={pipeline_count}")
        result = check_company(
            entry["rank"], company, pipeline_count, ai_count, boards_lookup, session
        )
        results.append(result)

    print_report(results, str(target_date))

    errors = [r for r in results if r["status"] == "ats_error"]
    if errors:
        names = [r["company"] for r in errors]
        log.error(f"{len(errors)} ATS error(s) require investigation: {names}")
        sys.exit(1)

    warnings = [r for r in results if r["status"] == "warning"]
    if warnings:
        names = [r["company"] for r in warnings]
        log.warning(f"{len(warnings)} discrepancy warning(s): {names}")
        # Warnings are non-blocking; report but exit 0.

    log.info("Top-companies QA check complete.")


if __name__ == "__main__":
    main()
