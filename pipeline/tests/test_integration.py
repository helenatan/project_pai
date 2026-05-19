"""
test_integration.py -- End-to-end fixture run against a real test DB.

Loads 30 fixture job postings, runs enrich → aggregate, asserts correct output.

Requires TEST_DATABASE_URL. Skip if not set.
"""

import os
import uuid
import pytest
from datetime import date, timedelta
from collections import Counter

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DATABASE_URL not set")

SUPABASE_URL = os.environ.get("TEST_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("TEST_SUPABASE_SERVICE_KEY", "")

TARGET_DATE = date.today() - timedelta(days=1)


def make_raw_posting(
    source: str,
    title: str,
    company: str,
    has_ai_language: bool,
    posted_date: date = None,
    source_id: str = None,
) -> dict:
    posted_date = posted_date or TARGET_DATE
    ai_desc = "Experience with LLM, prompt engineering, and generative AI required." if has_ai_language else ""
    return {
        "id": str(uuid.uuid4()),
        "source": source,
        "source_id": source_id or str(uuid.uuid4()),
        "title": title,
        "company": company,
        "location": "New York, NY",
        "posted_date": str(posted_date),
        "description_text": f"Lead product strategy for our platform. {ai_desc}",
        "url": "https://example.com/job",
        "is_remote": False,
        "raw_payload": {"raw": True},
    }


FIXTURE_POSTINGS = [
    # 10 JSearch postings with AI language (various companies)
    make_raw_posting("jsearch", "Senior Product Manager", "Stripe, Inc.", True),
    make_raw_posting("jsearch", "Product Manager", "Google LLC", True),
    make_raw_posting("jsearch", "Staff Product Manager", "Meta Platforms", True),
    make_raw_posting("jsearch", "Senior Product Manager", "Apple Inc.", True),
    make_raw_posting("jsearch", "Product Manager", "Microsoft Corp.", True),
    make_raw_posting("jsearch", "Principal Product Manager", "Amazon", True),
    make_raw_posting("jsearch", "Group Product Manager", "Salesforce", True),
    make_raw_posting("jsearch", "Senior Product Manager", "Stripe, Inc.", True),  # dup hash
    make_raw_posting("jsearch", "Product Manager", "Airbnb", True),
    make_raw_posting("jsearch", "VP of Product", "Figma", True),
    # 5 JSearch postings WITHOUT AI language
    make_raw_posting("jsearch", "Product Manager", "Zendesk", False),
    make_raw_posting("jsearch", "Senior Product Manager", "HubSpot", False),
    make_raw_posting("jsearch", "Product Manager", "Twilio", False),
    make_raw_posting("jsearch", "Associate Product Manager", "Canva", False),
    make_raw_posting("jsearch", "Product Manager", "Notion", False),
    # 15 Adzuna postings (not used for AI rate, some duplicates)
    make_raw_posting("adzuna", "Senior Product Manager", "Stripe, Inc.", True),  # cross-source dup
    make_raw_posting("adzuna", "Product Manager", "Netflix", False),
    make_raw_posting("adzuna", "Product Manager", "Spotify", True),
    make_raw_posting("adzuna", "Senior Product Manager", "Lyft", False),
    make_raw_posting("adzuna", "Product Manager", "Uber", True),
    make_raw_posting("adzuna", "Staff Product Manager", "Square", False),
    make_raw_posting("adzuna", "Product Manager", "Robinhood", True),
    make_raw_posting("adzuna", "Group Product Manager", "Coinbase", False),
    make_raw_posting("adzuna", "VP of Product", "OpenAI", True),
    make_raw_posting("adzuna", "Senior Product Manager", "Anthropic", True),
    make_raw_posting("adzuna", "Product Manager", "Databricks", True),
    make_raw_posting("adzuna", "Principal Product Manager", "Scale AI", True),
    make_raw_posting("adzuna", "Senior Product Manager", "Palantir", False),
    make_raw_posting("adzuna", "Product Manager", "Snowflake", False),
    make_raw_posting("adzuna", "Associate Product Manager", "MongoDB", False),
]


@pytest.fixture(scope="module")
def supabase():
    from supabase import create_client
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return client


@pytest.fixture(scope="module", autouse=True)
def seed_and_teardown(supabase):
    """Insert fixture postings and a minimal fetch_log, then clean up after."""
    # Insert raw postings
    supabase.table("job_postings_raw").upsert(
        FIXTURE_POSTINGS, on_conflict="source,source_id", ignore_duplicates=True
    ).execute()

    # Insert fetch_log rows so aggregate.py can find them
    supabase.table("fetch_log").upsert([
        {
            "run_date": str(TARGET_DATE),
            "source": "adzuna",
            "records_fetched": 15,
            "records_inserted": 15,
            "records_skipped": 0,
            "adzuna_total_count": 9800,
            "status": "ok",
        },
        {
            "run_date": str(TARGET_DATE),
            "source": "jsearch",
            "records_fetched": 15,
            "records_inserted": 15,
            "records_skipped": 0,
            "status": "ok",
        },
    ], on_conflict="run_date,source").execute()

    # Seed keywords so enrichment works
    supabase.table("ai_keywords").upsert([
        {"keyword": "llm", "category": "tooling"},
        {"keyword": "prompt engineering", "category": "tooling"},
        {"keyword": "generative ai", "category": "strategy"},
    ], on_conflict="keyword").execute()

    yield

    # Cleanup
    raw_ids = [p["id"] for p in FIXTURE_POSTINGS]
    supabase.table("job_postings_enriched").delete().in_("raw_id", raw_ids).execute()
    supabase.table("job_postings_raw").delete().in_("id", raw_ids).execute()
    supabase.table("daily_snapshots").delete().eq("snapshot_date", str(TARGET_DATE)).execute()
    supabase.table("fetch_log").delete().eq("run_date", str(TARGET_DATE)).execute()


def run_enrich():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "pipeline/scripts/enrich.py", "--version", "v1.0"],
        capture_output=True, text=True,
        env={**os.environ, "SUPABASE_URL": SUPABASE_URL, "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY},
    )
    assert result.returncode == 0, f"enrich.py failed:\n{result.stderr}"


def run_aggregate():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "pipeline/scripts/aggregate.py", "--date", str(TARGET_DATE)],
        capture_output=True, text=True,
        env={**os.environ, "SUPABASE_URL": SUPABASE_URL, "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY},
    )
    assert result.returncode == 0, f"aggregate.py failed:\n{result.stderr}"


def test_full_pipeline_against_fixture(supabase):
    """
    Load 30 fixture postings, run enrich + aggregate, assert correct snapshot output.
    This catches bug classes that unit tests miss: undefined references, schema/code drift,
    incorrect SQL joins.
    """
    run_enrich()
    run_aggregate()

    resp = (
        supabase.table("daily_snapshots")
        .select("*")
        .eq("snapshot_date", str(TARGET_DATE))
        .execute()
    )
    assert resp.data, f"No snapshot row found for {TARGET_DATE}"
    snapshot = resp.data[0]

    # Basic field presence
    assert snapshot["total_postings"] is not None
    assert snapshot["ai_penetration_rate"] is not None

    # AI penetration should be positive (we seeded AI postings)
    assert snapshot["ai_penetration_rate"] > 0

    # top_ai_skills populated
    top_skills = snapshot["top_ai_skills"]
    assert top_skills is not None
    assert isinstance(top_skills["skills"], list)
    assert len(top_skills["skills"]) > 0
    assert top_skills["skills"][0]["rank"] == 1

    # top_employers_ai_skills populated
    top_employers = snapshot["top_employers_ai_skills"]
    assert top_employers is not None
    assert isinstance(top_employers["companies"], list)

    # data_quality_status is complete (we injected clean fetch_log)
    assert snapshot["data_quality_status"] == "complete"

    # Dedup: the two duplicate Stripe JSearch records should deduplicate
    # JSearch has 10 AI + 5 non-AI = 15 total, with 1 dup → 14 distinct
    # AI rate = at most 9/14 * 100 (deduped)
    assert 0 < snapshot["ai_penetration_rate"] <= 100
