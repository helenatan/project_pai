-- Migration 001_initial_schema.sql
-- PM Adaptation Index -- initial schema

-- ── RAW STORAGE (append-only, never mutate) ───────────────────────────────────
CREATE TABLE job_postings_raw (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  source          TEXT NOT NULL CHECK (source IN ('adzuna', 'jsearch')),
  source_id       TEXT NOT NULL,
  title           TEXT,
  company         TEXT,
  location        TEXT,
  posted_date     DATE,
  description_text TEXT,
  url             TEXT,
  is_remote       BOOLEAN,
  raw_payload     JSONB NOT NULL,
  UNIQUE (source, source_id)
);

CREATE INDEX idx_raw_fetched_at   ON job_postings_raw (fetched_at);
CREATE INDEX idx_raw_posted_date  ON job_postings_raw (posted_date);
CREATE INDEX idx_raw_source       ON job_postings_raw (source);

-- ── ENRICHED LAYER (reprocessable, versioned) ─────────────────────────────────
CREATE TABLE job_postings_enriched (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_id                UUID NOT NULL REFERENCES job_postings_raw(id),
  enriched_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  pipeline_version      TEXT NOT NULL DEFAULT 'v1.0',

  dedup_hash            TEXT,
  company_normalized    TEXT,

  normalized_title      TEXT,
  seniority_level       TEXT,

  has_ai_requirement    BOOLEAN NOT NULL DEFAULT false,
  ai_keyword_matches    TEXT[],

  UNIQUE (raw_id, pipeline_version)
);

CREATE INDEX idx_enriched_raw_id           ON job_postings_enriched (raw_id);
CREATE INDEX idx_enriched_pipeline_version ON job_postings_enriched (pipeline_version);
CREATE INDEX idx_enriched_dedup_hash       ON job_postings_enriched (dedup_hash);
CREATE INDEX idx_enriched_has_ai           ON job_postings_enriched (has_ai_requirement);

-- ── DAILY SNAPSHOTS (what the dashboard reads) ────────────────────────────────
CREATE TABLE daily_snapshots (
  snapshot_date              DATE PRIMARY KEY,
  computed_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  pipeline_version           TEXT NOT NULL,
  data_quality_status        TEXT NOT NULL DEFAULT 'complete',
  data_quality_notes         TEXT,

  -- Volume (Adzuna)
  total_postings             INTEGER,
  total_postings_7day_avg    DECIMAL(10,2),
  new_postings_today         INTEGER,
  new_postings_7day_avg      DECIMAL(8,2),

  -- AI penetration (JSearch)
  ai_penetration_rate        DECIMAL(5,2),
  ai_penetration_7day_avg    DECIMAL(5,2),

  -- Dedup quality
  total_postings_raw         INTEGER,
  dedup_rate                 DECIMAL(5,2),

  -- Top 10 AI skills today (JSearch)
  -- {total_ai_postings_today, skills: [{rank, keyword, count, prev_7day_daily_avg, direction}]}
  top_ai_skills              JSONB,

  -- Top 10 companies with AI PM demand (7-day rolling, JSearch)
  -- {window_days, window_end, companies: [{rank, company, count, prev_count, direction}]}
  top_employers_ai_skills    JSONB,

  -- Weekly digest (Saturdays only)
  summary_text               TEXT,
  digest_generated_at        TIMESTAMPTZ
);

-- ── PIPELINE OBSERVABILITY ────────────────────────────────────────────────────
CREATE TABLE fetch_log (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  run_date            DATE NOT NULL,
  source              TEXT NOT NULL CHECK (source IN ('adzuna', 'jsearch')),
  records_fetched     INTEGER NOT NULL DEFAULT 0,
  records_inserted    INTEGER NOT NULL DEFAULT 0,
  records_skipped     INTEGER NOT NULL DEFAULT 0,
  adzuna_total_count  INTEGER,
  status              TEXT NOT NULL,
  error_message       TEXT,
  UNIQUE (run_date, source)
);

CREATE INDEX idx_fetch_log_run_date ON fetch_log (run_date);

-- ── REFERENCE TABLES ──────────────────────────────────────────────────────────
CREATE TABLE ai_keywords (
  id              SERIAL PRIMARY KEY,
  keyword         TEXT NOT NULL UNIQUE,
  category        TEXT NOT NULL,
  added_version   TEXT NOT NULL DEFAULT 'v1.0',
  added_date      DATE NOT NULL DEFAULT CURRENT_DATE,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  notes           TEXT
);

-- ── ROW LEVEL SECURITY ────────────────────────────────────────────────────────
ALTER TABLE daily_snapshots        ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_postings_raw       ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_postings_enriched  ENABLE ROW LEVEL SECURITY;
ALTER TABLE fetch_log              ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_keywords            ENABLE ROW LEVEL SECURITY;

-- Public read access to daily_snapshots only
CREATE POLICY "Public read access" ON daily_snapshots
  FOR SELECT USING (true);

-- No policies on other tables = no access for anon key
