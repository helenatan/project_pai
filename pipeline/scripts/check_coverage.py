"""
check_coverage.py -- Fail the pipeline when a source went silent or thin.

Runs after aggregate.py (so the degraded snapshot is already written) and
before digest.py (so a digest is never sent on broken coverage).

For each expected source on run_date:
  - missing fetch_log row      -> FAIL
  - status == failed           -> FAIL (includes silent zeros)
  - records_fetched below floor -> FAIL, where floor = median of the trailing
    BASELINE_DAYS of non-zero fetches / FLOOR_DIVISOR. Zero-row days are
    excluded from the baseline so a long outage cannot drag the floor to zero.
    The floor check is skipped when fewer than MIN_BASELINE_ROWS exist.

Exit codes:
  0  every expected source is present, non-failed and above its floor
  1  at least one source fails a check (details printed as a table)
"""

import os
import sys
import logging
from datetime import date, timedelta
from statistics import median

from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EXPECTED_SOURCES = ["jsearch", "greenhouse", "ashby"]
BASELINE_DAYS = 28
MIN_BASELINE_ROWS = 5
FLOOR_DIVISOR = 3


def evaluate(row: dict | None, baseline: list[int]) -> tuple[str, str]:
    """Pure check for one source. Returns (verdict, detail); verdict is PASS or FAIL."""
    if row is None:
        return "FAIL", "no fetch_log row"
    if row["status"] == "failed":
        return "FAIL", f"status=failed ({row.get('error_message') or ''})"[:160]
    fetched = row["records_fetched"] or 0
    usable = [b for b in baseline if b > 0]
    if len(usable) < MIN_BASELINE_ROWS:
        return "PASS", f"fetched={fetched} (baseline too small: {len(usable)} rows)"
    floor = median(usable) / FLOOR_DIVISOR
    if fetched < floor:
        return "FAIL", f"fetched={fetched} below floor {floor:.1f} (median {median(usable):.0f} over {len(usable)} days)"
    return "PASS", f"fetched={fetched}, floor {floor:.1f}"


def get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-date", default=None, help="Override run date (YYYY-MM-DD)")
    args = parser.parse_args()
    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today() - timedelta(days=1)
    since = run_date - timedelta(days=BASELINE_DAYS)

    supabase = get_supabase()
    rows = (
        supabase.table("fetch_log")
        .select("run_date,source,records_fetched,status,error_message")
        .gte("run_date", str(since))
        .lte("run_date", str(run_date))
        .in_("source", EXPECTED_SOURCES)
        .execute()
        .data
    )
    today_by_source = {r["source"]: r for r in rows if r["run_date"] == str(run_date)}
    baseline_by_source = {s: [] for s in EXPECTED_SOURCES}
    for r in rows:
        if r["run_date"] != str(run_date):
            baseline_by_source[r["source"]].append(r["records_fetched"] or 0)

    failures = 0
    print(f"\nCoverage check for run_date={run_date}\n")
    print(f"{'source':<12}{'verdict':<8}detail")
    for s in EXPECTED_SOURCES:
        verdict, detail = evaluate(today_by_source.get(s), baseline_by_source[s])
        print(f"{s:<12}{verdict:<8}{detail}")
        if verdict == "FAIL":
            failures += 1
    print()

    if failures:
        log.error(f"{failures} source(s) failed coverage check. Exiting non-zero.")
        sys.exit(1)
    log.info("All sources pass coverage check.")


if __name__ == "__main__":
    main()
