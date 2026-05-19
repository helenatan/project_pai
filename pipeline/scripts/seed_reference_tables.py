"""
seed_reference_tables.py -- Seed ai_keywords table from pipeline/data/ai_keywords.csv.
Safe to re-run: uses upsert on keyword (unique constraint).
"""

import csv
import logging
import os
from pathlib import Path

from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

DATA_DIR = Path(__file__).parent.parent / "data"


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def seed_ai_keywords(supabase: Client):
    csv_path = DATA_DIR / "ai_keywords.csv"
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "keyword": row["keyword"].strip(),
                    "category": row["category"].strip(),
                    "notes": row.get("notes", "").strip() or None,
                    "added_version": "v1.0",
                    "is_active": True,
                }
            )

    supabase.table("ai_keywords").upsert(rows, on_conflict="keyword").execute()
    log.info(f"Seeded {len(rows)} AI keywords")


def main():
    supabase = get_supabase()
    seed_ai_keywords(supabase)
    log.info("Reference tables seeded.")


if __name__ == "__main__":
    main()
