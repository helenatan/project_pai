-- Migration 005: Add last_seen_date and is_us to job_postings_raw.
--
-- last_seen_date: mutable, updated on every fetch_employers run for each active job.
-- Unlike run_date/posted_date (immutable first-seen markers), this tracks whether a
-- job is still live on its employer board. Used for the 7-day active-job company count.
--
-- is_us: set at ingest time from location text. Filters company counts to US roles only,
-- preventing London/Singapore/Tokyo postings from inflating company totals.

-- ── 1. last_seen_date ─────────────────────────────────────────────────────────
ALTER TABLE job_postings_raw ADD COLUMN last_seen_date DATE;

-- Backfill employer-board records: best estimate is first-seen (run_date).
-- fetch_employers.py will overwrite with today's date on its next run.
UPDATE job_postings_raw
SET last_seen_date = run_date
WHERE source IN ('greenhouse', 'ashby', 'lever')
  AND last_seen_date IS NULL;

CREATE INDEX idx_raw_last_seen_date ON job_postings_raw (last_seen_date);

-- ── 2. is_us ─────────────────────────────────────────────────────────────────
ALTER TABLE job_postings_raw ADD COLUMN is_us BOOLEAN;

-- JSearch and Adzuna are US-only by query construction.
UPDATE job_postings_raw SET is_us = TRUE WHERE source IN ('adzuna', 'jsearch');

-- Employer-board backfill: detect US from location text.
-- fetch_employers.py will set this correctly on new inserts going forward.
UPDATE job_postings_raw
SET is_us = (
    location IS NOT NULL AND (
        lower(location) LIKE '%united states%'  OR
        lower(location) LIKE '%san francisco%'  OR
        lower(location) LIKE '%new york%'        OR
        lower(location) LIKE '%seattle%'         OR
        lower(location) LIKE '%chicago%'         OR
        lower(location) LIKE '%atlanta%'         OR
        lower(location) LIKE '%boston%'          OR
        lower(location) LIKE '%austin%'          OR
        lower(location) LIKE '%los angeles%'     OR
        lower(location) LIKE '%denver%'          OR
        lower(location) LIKE '%miami%'           OR
        lower(location) LIKE '%houston%'         OR
        lower(location) LIKE '%portland%'        OR
        lower(location) LIKE '%california%'      OR
        lower(location) LIKE '%new jersey%'      OR
        lower(location) LIKE '%washington, d%'   OR
        lower(location) LIKE '%remote in the us%' OR
        lower(location) LIKE '%remote-us%'       OR
        lower(location) LIKE '%us remote%'       OR
        lower(location) LIKE '%us - remote%'     OR
        lower(location) LIKE '%- us%'
    )
)
WHERE source IN ('greenhouse', 'ashby', 'lever')
  AND is_us IS NULL;

-- NULL is_us = location could not be determined; treated as non-US in company count.

CREATE INDEX idx_raw_is_us ON job_postings_raw (is_us);
