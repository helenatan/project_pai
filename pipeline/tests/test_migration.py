"""
test_migration.py -- Verify 001_initial_schema.sql creates the expected tables and RLS policies.

Requires a real Postgres connection. Set TEST_DATABASE_URL env var.
Skip if not set (CI without a test DB).
"""

import os
import pytest

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture(scope="module")
def conn():
    import psycopg2
    c = psycopg2.connect(TEST_DB_URL)
    yield c
    c.close()


EXPECTED_TABLES = {
    "job_postings_raw",
    "job_postings_enriched",
    "daily_snapshots",
    "fetch_log",
    "ai_keywords",
}

RLS_TABLES = {
    "job_postings_raw",
    "job_postings_enriched",
    "daily_snapshots",
    "fetch_log",
    "ai_keywords",
}


def test_migration_creates_all_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
        """)
        tables = {row[0] for row in cur.fetchall()}
    for expected in EXPECTED_TABLES:
        assert expected in tables, f"Table '{expected}' not found after migration"


def test_migration_rls_enabled(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT relname, relrowsecurity
            FROM pg_class
            WHERE relkind = 'r'
              AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        """)
        rows = {row[0]: row[1] for row in cur.fetchall()}
    for table in RLS_TABLES:
        assert rows.get(table) is True, f"RLS not enabled on '{table}'"


def test_migration_public_read_policy_on_snapshots(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT policyname, cmd
            FROM pg_policies
            WHERE tablename = 'daily_snapshots'
              AND schemaname = 'public'
        """)
        policies = cur.fetchall()
    assert any(
        "select" in (cmd or "").lower() for _, cmd in policies
    ), "No SELECT policy found on daily_snapshots"


def test_migration_unique_constraints(conn):
    with conn.cursor() as cur:
        # job_postings_raw UNIQUE (source, source_id)
        cur.execute("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'job_postings_raw'::regclass
              AND contype = 'u'
        """)
        raw_constraints = {row[0] for row in cur.fetchall()}
        assert raw_constraints, "No unique constraint on job_postings_raw"

        # fetch_log UNIQUE (run_date, source)
        cur.execute("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'fetch_log'::regclass
              AND contype = 'u'
        """)
        fetch_constraints = {row[0] for row in cur.fetchall()}
        assert fetch_constraints, "No unique constraint on fetch_log"
