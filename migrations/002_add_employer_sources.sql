-- Migration 002_add_employer_sources.sql
-- Extend source CHECK constraint to allow 'greenhouse' and 'ashby' as data sources.
-- These cover AI-native employers (Anthropic, OpenAI, DeepMind, xAI, etc.)
-- that Adzuna/JSearch don't reliably index.

ALTER TABLE job_postings_raw DROP CONSTRAINT job_postings_raw_source_check;
ALTER TABLE job_postings_raw ADD CONSTRAINT job_postings_raw_source_check
  CHECK (source IN ('adzuna', 'jsearch', 'greenhouse', 'ashby'));

ALTER TABLE fetch_log DROP CONSTRAINT fetch_log_source_check;
ALTER TABLE fetch_log ADD CONSTRAINT fetch_log_source_check
  CHECK (source IN ('adzuna', 'jsearch', 'greenhouse', 'ashby'));
