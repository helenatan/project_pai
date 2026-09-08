"""
backup.py -- Dump daily_snapshots, job_postings_raw, job_postings_enriched, fetch_log to JSON files.
Run Saturdays by .github/workflows/backup.yml. All four dumps are uploaded as a
90-day GitHub Actions artifact; the two small ones (snapshots, fetch_log) are
also committed gzipped to backups/ as the durable point-in-time record.
Exits non-zero if any table fails to dump.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

TABLES = [
    ("daily_snapshots", "backup_snapshots.json"),
    ("job_postings_raw", "backup_raw.json"),
    ("job_postings_enriched", "backup_enriched.json"),
    ("fetch_log", "backup_fetch_log.json"),
]

PAGE_SIZE = 1000


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def dump_table(supabase: Client, table: str, output_file: str):
    all_rows = []
    offset = 0
    while True:
        resp = (
            supabase.table(table)
            .select("*")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        rows = resp.data
        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    with open(output_file, "w") as f:
        json.dump(
            {"table": table, "exported_at": datetime.now(timezone.utc).isoformat(), "rows": all_rows},
            f,
            default=str,
            indent=2,
        )
    log.info(f"Backed up {len(all_rows)} rows from {table} → {output_file}")


def main():
    supabase = get_supabase()
    failed = []
    for table, output_file in TABLES:
        try:
            dump_table(supabase, table, output_file)
        except Exception as e:
            log.error(f"Failed to backup {table}: {e}")
            failed.append(table)
    if failed:
        log.error(f"Backup incomplete, tables failed: {failed}")
        sys.exit(1)
    log.info("Backup complete.")


if __name__ == "__main__":
    main()
