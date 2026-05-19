"""
backup.py -- Dump daily_snapshots, job_postings_raw, job_postings_enriched, fetch_log to JSON files.
Run Saturdays by the daily pipeline workflow. Output files are uploaded as GitHub Actions artifacts.
"""

import json
import logging
import os
from datetime import datetime

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
            {"table": table, "exported_at": datetime.utcnow().isoformat(), "rows": all_rows},
            f,
            default=str,
            indent=2,
        )
    log.info(f"Backed up {len(all_rows)} rows from {table} → {output_file}")


def main():
    supabase = get_supabase()
    for table, output_file in TABLES:
        try:
            dump_table(supabase, table, output_file)
        except Exception as e:
            log.error(f"Failed to backup {table}: {e}")
    log.info("Backup complete.")


if __name__ == "__main__":
    main()
