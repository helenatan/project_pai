-- Migration 006: Reset polluted last_seen_date values.
--
-- Migration 005 originally backfilled last_seen_date = run_date for existing
-- employer-board rows. That was wrong: a job already removed from its board
-- still received a recent last_seen_date, so it stayed inside the 7-day
-- active-job window and inflated company counts (e.g. OpenAI showed 23).
--
-- last_seen_date must only ever be set by an actual fetch_employers.py run that
-- confirms the job is still live. Reset it to NULL for all employer-board rows;
-- the next pipeline run repopulates it accurately for every currently-live job.
-- (Stale rows -- removed jobs, now-excluded false positives -- stay NULL and
-- are correctly dropped from the count.)

UPDATE job_postings_raw
SET last_seen_date = NULL
WHERE source IN ('greenhouse', 'ashby', 'lever');
