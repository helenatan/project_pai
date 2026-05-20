-- Migration 004_add_run_date.sql
-- Add run_date to job_postings_raw: the pipeline run date a posting was first
-- ingested on. Because the raw table is append-only and every fetcher upserts
-- with ON CONFLICT DO NOTHING, run_date is written exactly once and never
-- mutated -- making it an immutable first-seen marker.
--
-- This replaces the Adzuna-only `records_inserted` heuristic for the
-- "new PM jobs posted today" metric: new_jobs_on() counts deduplicated jobs
-- first seen on a given day across ALL sources.

-- ── 1. COLUMN + BACKFILL ──────────────────────────────────────────────────────
ALTER TABLE job_postings_raw ADD COLUMN run_date DATE;

-- Backfill existing rows from fetched_at (the original, immutable insert time),
-- converted to Pacific time since the pipeline runs at 6am PT.
UPDATE job_postings_raw
SET run_date = (fetched_at AT TIME ZONE 'America/Los_Angeles')::date
WHERE run_date IS NULL;

ALTER TABLE job_postings_raw ALTER COLUMN run_date SET NOT NULL;

CREATE INDEX idx_raw_run_date ON job_postings_raw (run_date);

-- ── 2. new_jobs_on(day): deduplicated count of jobs first seen on `day` ───────
-- A job -- identified by dedup_hash (normalized company + title) -- is "new on
-- day D" if it was ingested with run_date = D and was never ingested on an
-- earlier run_date. Spans all sources; counts a cross-source duplicate once.
CREATE OR REPLACE FUNCTION new_jobs_on(day DATE, version TEXT DEFAULT 'v1.0')
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
  WITH todays AS (
    SELECT DISTINCT e.dedup_hash
    FROM job_postings_raw r
    JOIN job_postings_enriched e ON e.raw_id = r.id
    WHERE r.run_date = day
      AND e.pipeline_version = version
      AND e.dedup_hash IS NOT NULL
  )
  SELECT count(*)::int
  FROM todays t
  WHERE NOT EXISTS (
    SELECT 1
    FROM job_postings_raw r2
    JOIN job_postings_enriched e2 ON e2.raw_id = r2.id
    WHERE e2.dedup_hash = t.dedup_hash
      AND e2.pipeline_version = version
      AND r2.run_date < day
  );
$$;
