# Engineering Requirements: The PM Adaptation Index
### Technical Specification for the MVP

**Status:** v1.3
**Author:** Helena
**Last Updated:** May 2026
**Companion doc:** PRD v1.0
**Scope:** Everything required to ship the MVP. Nothing beyond it.

---

## 1. System Overview

The system has four components that run in sequence **every day at 6am PT**:

```
[Adzuna API] ─┐
               ├─► [Fetcher] ─► [job_postings_raw] ─► [Enricher] ─► [job_postings_enriched] ─► [Aggregator] ─► [daily_snapshots] ─► [Digest Generator*] ─► [Email Send*]
[JSearch API] ─┘                                                                                                                            │
                                                                                                                                            ▼
                                                                                                                                   [React Dashboard]
```

*Digest generation and email send run **Saturdays only**, not daily. Daily data accumulates silently; the digest surfaces the week's signal once a week.

**Why daily instead of weekly:** End-to-end validation happens in 24 hours, not 7 days. A broken fetch, enrichment error, or DB write failure is caught the next morning. The pipeline logic is identical to a weekly design -- the only changes are the cron schedule and the fetch filter (pull only yesterday's postings each day rather than paginating the full corpus).

The frontend reads only from `daily_snapshots`. It never queries raw or enriched tables directly.

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | Pipeline scripts |
| Database | Supabase (Postgres 15) | Free tier sufficient for MVP |
| Frontend | React 18 + Recharts | Single page, no routing needed for MVP |
| Hosting (frontend) | Vercel | Free tier |
| Hosting (backend) | GitHub Actions | Cron runs entirely in Actions -- no server needed |
| Email | Buttondown | Free up to 1,000 subscribers; simple API |
| AI | Anthropic API (claude-sonnet-4-20250514) | Digest generation only for MVP |
| Secrets management | GitHub Actions Secrets | API keys stored as repo secrets |
| Version control | GitHub | Private repo |

**No backend server is needed for the MVP.** The pipeline runs as GitHub Actions jobs. The frontend reads directly from Supabase via the public read-only client key. This keeps infra at zero cost and zero maintenance burden.

---

## 3. Database Schema

### 3.1 Raw Storage (append-only, never mutate)

```sql
-- Migration 001_initial_schema.sql

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

CREATE INDEX idx_raw_fetched_at ON job_postings_raw (fetched_at);
CREATE INDEX idx_raw_posted_date ON job_postings_raw (posted_date);
CREATE INDEX idx_raw_source ON job_postings_raw (source);
```

**Rules:**
- Never UPDATE or DELETE from this table
- `raw_payload` stores the complete API response object -- every field, even unused ones
- `UNIQUE (source, source_id)` is the primary dedup guard -- enforced at DB level, not just application level
- `posted_date` is when the employer posted the job; `fetched_at` is when the cron pulled it

### 3.2 Enriched Layer (reprocessable, versioned)

```sql
-- Migration 001_initial_schema.sql (continued)

CREATE TABLE job_postings_enriched (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_id                UUID NOT NULL REFERENCES job_postings_raw(id),
  enriched_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  pipeline_version      TEXT NOT NULL DEFAULT 'v1.0',

  -- Deduplication
  dedup_hash            TEXT,
  company_normalized    TEXT,           -- normalized for grouping in top-companies aggregation

  -- Title normalization
  normalized_title      TEXT,           -- 'PM' | 'Senior PM' | 'Staff PM' | 'Director' | 'VP' | 'APM' | 'Other'
  seniority_level       TEXT,           -- 'junior' | 'mid' | 'senior' | 'staff' | 'director' | 'vp' | 'unknown'

  -- AI signal (binary detection from full job description text)
  has_ai_requirement    BOOLEAN NOT NULL DEFAULT false,
  ai_keyword_matches    TEXT[],         -- which keywords from the list matched

  UNIQUE (raw_id, pipeline_version)
);

CREATE INDEX idx_enriched_raw_id ON job_postings_enriched (raw_id);
CREATE INDEX idx_enriched_pipeline_version ON job_postings_enriched (pipeline_version);
CREATE INDEX idx_enriched_dedup_hash ON job_postings_enriched (dedup_hash);
CREATE INDEX idx_enriched_has_ai ON job_postings_enriched (has_ai_requirement);
```

**Rules:**
- `pipeline_version` is set at enrichment time and never changed
- When the enrichment logic improves, bump version and reprocess -- do not update existing rows
- Query analytics using `WHERE pipeline_version = (SELECT MAX(pipeline_version) FROM job_postings_enriched)` or hardcode current version in the aggregation script
- Schema is intentionally minimal for the MVP. Forward-looking columns (sector, ai_requirement_type, ai_is_additive, is_ai_era_title, etc.) are added via migration when each post-MVP feature ships -- not pre-allocated as NULL placeholders

### 3.3 Daily Snapshots (what the dashboard reads)

```sql
-- Migration 001_initial_schema.sql (continued)

CREATE TABLE daily_snapshots (
  snapshot_date              DATE PRIMARY KEY,
  computed_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  pipeline_version           TEXT NOT NULL,
  data_quality_status        TEXT NOT NULL DEFAULT 'complete',  -- 'complete' | 'partial' | 'degraded'
  data_quality_notes         TEXT,                              -- e.g. "JSearch fetch failed -- 0 records this source"

  -- Volume (Adzuna)
  total_postings             INTEGER,                           -- live count of active US PM postings (Adzuna)
  total_postings_7day_avg    DECIMAL(10,2),                     -- 7-day rolling avg of total_postings
  new_postings_today         INTEGER,                           -- fresh listings fetched today
  new_postings_7day_avg      DECIMAL(8,2),                      -- 7-day rolling avg of new_postings_today

  -- AI penetration (JSearch) -- daily rate, with rolling avg for hero-metric comparison
  ai_penetration_rate        DECIMAL(5,2),                      -- % of TODAY's JSearch postings with AI requirement
  ai_penetration_7day_avg    DECIMAL(5,2),                      -- 7-day rolling avg of ai_penetration_rate

  -- Dedup quality
  total_postings_raw         INTEGER,                           -- pre-dedup record count today
  dedup_rate                 DECIMAL(5,2),                      -- % of today's records that were duplicates

  -- Top 10 AI skills today (JSearch full-text matching)
  -- Shape: {total_ai_postings_today, skills: [{rank, keyword, count, prev_7day_daily_avg, direction}]}
  -- direction: 'rising' | 'flat' | 'falling' | 'new'
  top_ai_skills              JSONB,

  -- Top 10 companies whose PM postings mention AI skills (7-day rolling window, JSearch)
  -- Shape: {window_days, window_end, companies: [{rank, company, count, prev_count, direction}]}
  -- direction: 'up' | 'flat' | 'down' | 'new'
  top_employers_ai_skills    JSONB,

  -- Weekly digest (populated Saturdays only)
  summary_text               TEXT,
  digest_generated_at        TIMESTAMPTZ
);
```

**Rules:**
- One row per day
- This table is safe to truncate and recompute at any time
- The dashboard reads ONLY from this table
- `summary_text` and `digest_generated_at` are populated Saturdays only -- dashboard shows last Saturday's digest on other days
- `top_ai_skills` and `top_employers_ai_skills` are populated daily by `aggregate.py`
- `data_quality_status = 'partial'` means at least one source failed today; the snapshot is written but the frontend can surface a quiet badge
- Schema is intentionally minimal for the MVP. Forward-looking JSONB columns (sector_breakdown, role_emergence, additive_rate, etc.) are added via migration when their features ship -- not pre-allocated as NULL placeholders

### 3.4 Pipeline Observability

```sql
-- Migration 001_initial_schema.sql (continued)

-- One row per (source, run_date) -- written by fetch.py for every run
-- Read by aggregate.py to get adzuna_total_count and new_postings_today
-- Read by alerts to confirm both sources succeeded
CREATE TABLE fetch_log (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  run_date            DATE NOT NULL,
  source              TEXT NOT NULL CHECK (source IN ('adzuna', 'jsearch')),
  records_fetched     INTEGER NOT NULL DEFAULT 0,
  records_inserted    INTEGER NOT NULL DEFAULT 0,
  records_skipped     INTEGER NOT NULL DEFAULT 0,
  adzuna_total_count  INTEGER,            -- Adzuna only; NULL for JSearch
  status              TEXT NOT NULL,      -- 'ok' | 'partial' | 'failed'
  error_message       TEXT,
  UNIQUE (run_date, source)
);

CREATE INDEX idx_fetch_log_run_date ON fetch_log (run_date);
```

### 3.5 Reference Tables

```sql
-- Migration 001_initial_schema.sql (continued)

-- AI keywords: stored in DB, seeded from CSV in /pipeline/data/ai_keywords.csv
CREATE TABLE ai_keywords (
  id              SERIAL PRIMARY KEY,
  keyword         TEXT NOT NULL UNIQUE,
  category        TEXT NOT NULL,          -- 'tooling' | 'strategy' | 'ops' | 'ethics' | 'generic'
  added_version   TEXT NOT NULL DEFAULT 'v1.0',
  added_date      DATE NOT NULL DEFAULT CURRENT_DATE,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  notes           TEXT
);
```

`company_sector_lookup` is intentionally NOT part of the MVP migration. It is added when the sector module ships (post-MVP) via its own migration.

---

## 4. Data Pipeline

All pipeline scripts live in `/pipeline/scripts/`. They are run in sequence by the GitHub Actions cron.

### 4.1 Script: fetch.py

**Purpose:** Pull PM job listings from Adzuna and JSearch for the **previous 24 hours**. Write raw records to `job_postings_raw`. Skip records that already exist via unique constraint.

**Daily fetch strategy:** Rather than paginating the full corpus each run (80-100 API calls), each daily run fetches only new postings from the past 24 hours. This keeps each run to 10-20 API calls, well within Adzuna's 250 request/day limit.

**Adzuna fetch:**
```
GET https://api.adzuna.com/v1/api/jobs/us/search/{page}
  ?app_id={ADZUNA_APP_ID}
  &app_key={ADZUNA_APP_KEY}
  &what=product+manager
  &where=united+states
  &results_per_page=50
  &date_from={YESTERDAY_ISO}        ← key parameter: only new postings
  &content-type=application/json
```
- `date_from` = yesterday's date in `YYYY-MM-DD` format
- Paginate until empty response (expect 2-5 pages per day, not 80-100)
- Target fields: `id` → source_id, `title`, `company.display_name`, `location.display_name`, `created` → posted_date, `description` → description_text (truncated -- used for counting only), `redirect_url` → url
- Store complete response in `raw_payload`
- Rate limit: 1 request/second, max 25/min, 250/day

**Also fetch total count (for volume metric):**
```
GET https://api.adzuna.com/v1/api/jobs/us/search/1
  ?app_id=...&app_key=...&what=product+manager&results_per_page=1
```
The `count` field in this response is the total number of active PM postings in the US right now. Store this separately as `adzuna_total_count` in the daily snapshot -- it is the volume metric, independent of what was posted yesterday.

**JSearch fetch:**
```
GET https://jsearch.p.rapidapi.com/search
  ?query=product+manager+in+united+states
  &page=1
  &num_pages=3
  &date_posted=today
Headers: X-RapidAPI-Key: {JSEARCH_API_KEY}
```
- `date_posted=today` limits to recent postings only
- 3 pages maximum per day -- sufficient for daily delta, not over-fetching
- Target fields: `job_id` → source_id, `job_title`, `employer_name`, `job_city`/`job_state`, `job_posted_at_datetime_utc`, `job_description` (full text -- used for AI keyword matching), `job_apply_link`, `job_is_remote`
- Store complete response in `raw_payload`

**Error handling and partial-failure semantics:**
- Wrap each API call in try/except
- On rate limit (429): wait 60 seconds, retry once
- On other error: log to stderr and record the error in `fetch_log.error_message`
- After each source completes, write a `fetch_log` row with `status`:
  - `'ok'` -- all calls succeeded, at least 1 record fetched
  - `'partial'` -- some calls failed but at least 1 record was inserted
  - `'failed'` -- 0 records inserted, all calls errored
- **At the end of fetch.py, exit with non-zero if either source has `status = 'failed'`.** This stops the pipeline run, fails the GitHub Action, and triggers the failure alert. This prevents the silent-partial scenario where a snapshot looks clean but is missing one source's data.
- If both sources have `status = 'partial'` or one is `'ok'` and one is `'partial'`, the run continues; `aggregate.py` sets `daily_snapshots.data_quality_status = 'partial'` and the frontend can surface a quiet badge.

### 4.2 Script: enrich.py

**Purpose:** Read unprocessed raw records, apply enrichment logic, write to `job_postings_enriched`.

**Run mode:** `python enrich.py --version v1.0 [--since YYYY-MM-DD] [--force-reprocess]`

- Default: process only raw records with no matching enriched row for current version
- `--since`: reprocess all records since a given date
- `--force-reprocess`: overwrite existing enriched rows for the given version

**Enrichment steps (in order):**

**Step 1: Title normalization**
```python
TITLE_PATTERNS = {
    'APM':          ['associate product manager', 'apm', 'junior product manager'],
    'PM':           ['product manager', ' pm ', 'product manager i', 'product manager ii'],
    'Senior PM':    ['senior product manager', 'sr. product manager', 'sr product manager', 'product manager iii'],
    'Staff PM':     ['staff product manager', 'principal product manager'],
    'Director':     ['director of product', 'director, product', 'group product manager', 'gpm'],
    'VP':           ['vp of product', 'vice president of product', 'vp product', 'head of product'],
    'CPO':          ['chief product officer', 'cpo'],
    'Other':        []  # fallback
}

SENIORITY_MAP = {
    'APM': 'junior', 'PM': 'mid', 'Senior PM': 'senior',
    'Staff PM': 'staff', 'Director': 'director', 'VP': 'vp', 'CPO': 'vp'
}
```
Apply pattern matching against lowercased title. First match wins. Store normalized_title and seniority_level.

**Step 2: AI keyword matching**
```python
# Load active keywords from DB
keywords = fetch_active_keywords()  # SELECT keyword FROM ai_keywords WHERE is_active = true

# Lowercase the description text
text = (raw.description_text or '').lower()

# Match: whole word or phrase match only
# Use regex: r'\b' + re.escape(keyword.lower()) + r'\b'
matches = [kw for kw in keywords if re.search(r'\b' + re.escape(kw.lower()) + r'\b', text)]

has_ai_requirement = len(matches) > 0
ai_keyword_matches = matches
```
Store `has_ai_requirement` (boolean) and `ai_keyword_matches` (array of matched terms).

**Step 3: Company normalization (needed for top-employers aggregation)**
```python
def normalize_company_name(raw_name: str) -> str:
    if not raw_name:
        return ''
    name = raw_name.lower().strip()
    # Strip common legal suffixes
    for suffix in [', inc.', ', inc', ', llc', ', llc.', ', ltd', ', ltd.',
                   ', corp.', ', corp', ', co.', ' inc.', ' inc', ' llc', ' ltd']:
        name = name.replace(suffix, '')
    # Strip extra whitespace
    return ' '.join(name.split())
```
Store `company_normalized` on the enriched record. This is the grouping key for the top-employers aggregation. Already used for dedup hash -- store it explicitly on the enriched row so the aggregation query does not need to recompute it.

**Step 4: Dedup hash**
```python
import hashlib

company_norm = normalize_company_name(raw.company or '')  # lowercase, strip Inc/LLC/Corp, strip whitespace
title_norm = normalize_title(raw.title or '')  # lowercase, strip whitespace

# Hash is intentionally NOT week-bucketed -- this lets a single hash represent
# the same role across any reporting window. Aggregations dedupe by hash WITHIN
# the window they care about (daily snapshot, 7-day company window, etc.).
dedup_input = f"{company_norm}|{title_norm}"
dedup_hash = hashlib.md5(dedup_input.encode()).hexdigest()
```

**Step 5: Write enriched record**
```python
# Insert or skip if already processed at this version
INSERT INTO job_postings_enriched (raw_id, pipeline_version, dedup_hash,
    company_normalized, normalized_title, seniority_level,
    has_ai_requirement, ai_keyword_matches)
VALUES (...)
ON CONFLICT (raw_id, pipeline_version) DO NOTHING  -- idempotent
```

### 4.3 Script: aggregate.py

**Purpose:** Read enriched records for yesterday, compute daily metrics, upsert into `daily_snapshots`.

**Run mode:** `python aggregate.py [--date YYYY-MM-DD]`

- Default: compute for yesterday
- `--date`: recompute for a specific date

**Computation:**

The aggregator is **idempotent**: every query that reads from `daily_snapshots` must scope strictly to `snapshot_date < target_date` so reprocessing an earlier day never pulls in future rows. Today's row is written by the final UPSERT — never read by computations earlier in this script.

```python
PIPELINE_VERSION = 'v1.0'
target_date      = sys.argv.get('--date') or yesterday()

# ── 0. PARTIAL-FAILURE PROPAGATION ──────────────────────────────────────────
adzuna_log  = SELECT * FROM fetch_log WHERE run_date = target_date AND source = 'adzuna'
jsearch_log = SELECT * FROM fetch_log WHERE run_date = target_date AND source = 'jsearch'

if not adzuna_log or not jsearch_log:
    data_quality_status = 'degraded'         # one source never even logged
elif adzuna_log.status == 'partial' or jsearch_log.status == 'partial':
    data_quality_status = 'partial'
else:
    data_quality_status = 'complete'

# ── 1. VOLUME (Adzuna live count) ────────────────────────────────────────────
total_postings     = adzuna_log.adzuna_total_count
new_postings_today = adzuna_log.records_inserted

# ── 2. ROLLING AVERAGES (strict upper bound: snapshot_date < target_date) ────
def rolling_7day_avg(column):
    rows = SELECT {column} FROM daily_snapshots
           WHERE snapshot_date >= target_date - INTERVAL '7 days'
             AND snapshot_date <  target_date              # ← upper bound is critical
             AND {column} IS NOT NULL
           ORDER BY snapshot_date DESC LIMIT 7
    return avg(rows) if len(rows) >= 3 else None          # NULL below 3 rows

total_postings_7day_avg = rolling_7day_avg('total_postings')
new_postings_7day_avg   = rolling_7day_avg('new_postings_today')

# ── 3. AI PENETRATION RATE (TODAY's daily rate, JSearch only) ────────────────
# Daily rate -- not a 7-day rolling rate. The rolling avg is computed separately
# from prior daily rates. This avoids the average-of-averages double-smoothing
# and means the hero metric reads as: "today's rate vs the prior 7-day average."
todays_jsearch = SELECT enriched
                 WHERE raw.posted_date = target_date
                   AND pipeline_version = PIPELINE_VERSION
                   AND raw.source = 'jsearch'

total_today  = COUNT DISTINCT dedup_hash IN todays_jsearch
ai_today     = COUNT DISTINCT dedup_hash WHERE has_ai_requirement = true

ai_penetration_rate     = (ai_today / total_today * 100) if total_today > 0 else None
ai_penetration_7day_avg = rolling_7day_avg('ai_penetration_rate')

# ── 4. TOP 10 AI SKILLS TODAY ────────────────────────────────────────────────
todays_ai_records = [r for r in todays_jsearch if r.has_ai_requirement]

keyword_counts = Counter()
for record in todays_ai_records:
    for kw in record.ai_keyword_matches:
        keyword_counts[kw] += 1

top_10_today = keyword_counts.most_common(10)

# Prior 7-day daily counts for trend comparison and for "new" detection
# IMPORTANT: keep the FULL prior history of keyword appearances (not just last 7 days)
# so we can correctly detect "new" -- a keyword that has never appeared before.
prev_7day_counts = Counter()
prev_7day_days_with_data = 0
prior_records = SELECT enriched WHERE raw.posted_date >= target_date - 7 days
                                  AND raw.posted_date <  target_date
                                  AND pipeline_version = PIPELINE_VERSION
                                  AND raw.source = 'jsearch'
                                  AND has_ai_requirement = true
for record in prior_records:
    for kw in record.ai_keyword_matches:
        prev_7day_counts[kw] += 1
prev_7day_days_with_data = COUNT DISTINCT raw.posted_date IN prior_records

ever_seen_keywords = SELECT DISTINCT unnest(ai_keyword_matches) FROM job_postings_enriched
                     WHERE raw.posted_date < target_date - 7 days
                       AND pipeline_version = PIPELINE_VERSION
                       AND has_ai_requirement = true
ever_seen = set(ever_seen_keywords) | set(prev_7day_counts.keys())

def skill_direction(kw, count, prev_total, days):
    if kw not in ever_seen:
        return 'new'                                       # first-ever appearance
    if days == 0 or prev_total == 0:
        return 'rising'                                    # seen before but quiet recently
    prev_daily_avg = prev_total / days                     # divide by days actually observed
    if count >= prev_daily_avg * 1.15: return 'rising'
    if count <= prev_daily_avg * 0.85: return 'falling'
    return 'flat'

top_ai_skills = {
    "total_ai_postings_today": len(todays_ai_records),
    "skills": [
        {
            "rank": i + 1,
            "keyword": kw,
            "count": count,
            "prev_7day_daily_avg": round(prev_7day_counts.get(kw, 0) / max(prev_7day_days_with_data, 1), 1),
            "direction": skill_direction(kw, count, prev_7day_counts.get(kw, 0), prev_7day_days_with_data),
        }
        for i, (kw, count) in enumerate(top_10_today)
    ],
}

# ── 5. TOP 10 COMPANIES (7-day rolling window) ───────────────────────────────
# Dedup by dedup_hash WITHIN the window (hash is no longer week-bucketed).
seven_day_ai = SELECT enriched
               WHERE raw.posted_date >= target_date - 7 days
                 AND raw.posted_date <  target_date          # exclusive upper bound
                 AND pipeline_version = PIPELINE_VERSION
                 AND raw.source = 'jsearch'
                 AND has_ai_requirement = true

prior_window_ai = SELECT enriched
                  WHERE raw.posted_date >= target_date - 14 days
                    AND raw.posted_date <  target_date - 7 days
                    AND pipeline_version = PIPELINE_VERSION
                    AND raw.source = 'jsearch'
                    AND has_ai_requirement = true

def count_companies(records):
    """Dedup by hash within the window, group by normalized company."""
    out = {}
    for r in records:
        if not r.company_normalized:                       # skip blank companies
            continue
        out.setdefault(r.company_normalized, set()).add(r.dedup_hash)
    return {company: len(hashes) for company, hashes in out.items()}

current = count_companies(seven_day_ai)
prior   = count_companies(prior_window_ai)
top_10  = sorted(current.items(), key=lambda x: x[1], reverse=True)[:10]

def company_direction(current_count, prev_count):
    # CRITICAL: check 'new' first -- otherwise (count > 0) always matches 'up' branch
    if prev_count == 0:           return 'new'
    if current_count > prev_count: return 'up'
    if current_count < prev_count: return 'down'
    return 'flat'

top_employers_ai_skills = {
    "window_days": 7,
    "window_end": str(target_date),
    "companies": [
        {
            "rank": i + 1,
            "company": company,
            "count": count,
            "prev_count": prior.get(company, 0),
            "direction": company_direction(count, prior.get(company, 0)),
        }
        for i, (company, count) in enumerate(top_10)
    ],
}

# ── 6. DEDUP QUALITY ─────────────────────────────────────────────────────────
total_postings_raw = COUNT(*) FROM enriched WHERE raw.posted_date = target_date
distinct_today     = COUNT DISTINCT dedup_hash FROM enriched WHERE raw.posted_date = target_date
dedup_rate = ((total_postings_raw - distinct_today) / total_postings_raw * 100) if total_postings_raw > 0 else 0

# ── 7. UPSERT (single source of truth for today's row) ───────────────────────
INSERT INTO daily_snapshots (
    snapshot_date, pipeline_version, computed_at, data_quality_status,
    total_postings, total_postings_7day_avg,
    new_postings_today, new_postings_7day_avg,
    ai_penetration_rate, ai_penetration_7day_avg,
    total_postings_raw, dedup_rate,
    top_ai_skills, top_employers_ai_skills
)
VALUES (...)
ON CONFLICT (snapshot_date) DO UPDATE SET
    computed_at = EXCLUDED.computed_at,
    pipeline_version = EXCLUDED.pipeline_version,
    data_quality_status = EXCLUDED.data_quality_status,
    ... -- update every column EXCEPT summary_text and digest_generated_at
```

**Edge cases:**
- `todays_jsearch` is empty: `top_ai_skills.skills = []`, `top_employers_ai_skills.companies = []`, `ai_penetration_rate = NULL` -- do not error
- All three 7-day averages require minimum 3 prior rows; return NULL below that threshold -- the frontend omits the delta entirely until sufficient history exists
- Company name normalizes to empty string: skipped in `count_companies`
- Fewer than 10 AI keywords or companies today: return however many exist (preserve rank order)
- Reprocessing an earlier date never pulls future-dated rows into rolling averages (strict `<` upper bound)

**All three hero metrics use the same 7-day-avg comparison baseline:**
- `total_postings` vs `total_postings_7day_avg`
- `new_postings_today` vs `new_postings_7day_avg`  -- 7-day window neutralizes weekday/weekend effects
- `ai_penetration_rate` vs `ai_penetration_7day_avg`

Consistent comparison windows mean a reader can interpret all three deltas the same way without learning different methodologies per metric.

### 4.4 Script: digest.py

**Purpose:** Runs **Saturdays only**. Read the past 7 days of daily snapshots, call Claude API, generate a weekly digest paragraph, update Saturday's snapshot row, send email via Buttondown.

**Saturday-only guard:**
```python
from datetime import date
if date.today().weekday() != 5:  # 5 = Saturday
    print("Not Saturday -- digest skipped")
    sys.exit(0)
```

**Claude API call:**
```python
SYSTEM_PROMPT = """
You are writing the weekly digest for The PM Adaptation Index, an empirical observatory
tracking how AI is reshaping the product management profession.

Your job: write exactly 3-4 sentences that:
1. Report the headline numbers (total postings, AI penetration rate) with WoW comparison
2. Call out the top AI skill(s) that dominated PM job postings this week
3. Name the leading companies hiring PMs with AI skills if the pattern is noteworthy
4. Interpret the signal honestly against the central thesis. If data is inconclusive, say so.

Tone: a curious, honest reporter. Not a cheerleader. Not an alarmist.
Do not editorialize beyond the data. Never use em dashes.
"""

# Build payload from the latest daily snapshot (Saturday)
payload = {
    "snapshot_date":            latest_snapshot.snapshot_date,
    "total_postings":           latest_snapshot.total_postings,
    "total_postings_7day_avg":  latest_snapshot.total_postings_7day_avg,
    "ai_penetration_rate":      latest_snapshot.ai_penetration_rate,
    "ai_penetration_7days_ago": snapshot_7days_ago.ai_penetration_rate,
    "top_ai_skills":            latest_snapshot.top_ai_skills,                       # full top 10
    "top_employers_ai_skills":  latest_snapshot.top_employers_ai_skills.companies[:5],  # top 5 for brevity
    "days_of_data":             count_of_snapshots_so_far
}

response = anthropic.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=350,   # room to cover 4 signals
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": f"Generate the digest for this data: {json.dumps(payload)}"}]
)
```

**No narrative status computation in the MVP.** The narrative status badge ("Evidence favors: Narrative A/B") is post-MVP per the PRD. `daily_snapshots` has no `narrative_status` column. The digest text may reference the narratives in prose but does not emit a structured status field.

**Email via Buttondown:**
```python
import requests

def send_digest_email(subject: str, body: str):
    requests.post(
        "https://api.buttondown.email/v1/emails",
        headers={"Authorization": f"Token {BUTTONDOWN_API_KEY}"},
        json={
            "subject": subject,
            "body": body,
            "status": "about_to_send"
        }
    )
```

---

## 5. GitHub Actions Workflows

### 5.1 Daily Pipeline (runs every day)

File: `.github/workflows/daily_pipeline.yml`

```yaml
name: Daily Pipeline

on:
  schedule:
    - cron: '0 14 * * *'   # Daily 6am PT (14:00 UTC)
  workflow_dispatch:         # allow manual trigger for testing

jobs:
  pipeline:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r pipeline/requirements.txt

      - name: Run fetcher
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          ADZUNA_APP_ID: ${{ secrets.ADZUNA_APP_ID }}
          ADZUNA_APP_KEY: ${{ secrets.ADZUNA_APP_KEY }}
          JSEARCH_API_KEY: ${{ secrets.JSEARCH_API_KEY }}
        run: python pipeline/scripts/fetch.py

      - name: Run enricher
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python pipeline/scripts/enrich.py --version v1.0

      - name: Run aggregator
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python pipeline/scripts/aggregate.py

      - name: Run digest (Saturdays only -- script self-guards)
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          BUTTONDOWN_API_KEY: ${{ secrets.BUTTONDOWN_API_KEY }}
        run: python pipeline/scripts/digest.py

      - name: Backup snapshots (Saturdays only)
        if: ${{ github.event.schedule == '0 14 * * 6' || (github.event_name == 'workflow_dispatch') }}
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: python pipeline/scripts/backup.py
        continue-on-error: true

      - name: Upload backup artifact (snapshots + raw + enriched)
        if: ${{ github.event.schedule == '0 14 * * 6' }}
        uses: actions/upload-artifact@v4
        with:
          name: pai-backup-${{ github.run_number }}
          path: |
            backup_snapshots.json
            backup_raw.json
            backup_enriched.json
            backup_fetch_log.json
          retention-days: 90

      # First-of-month: commit snapshot dump to repo for permanent record
      # (artifacts expire at 90 days; this is the durable copy)
      - name: Commit monthly snapshot to repo
        if: ${{ github.event.schedule == '0 14 * * 6' && github.event.schedule == '0 14 1 * *' }}
        run: |
          mkdir -p backups
          cp backup_snapshots.json "backups/snapshots_$(date +%Y%m).json"
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add backups/
          git commit -m "chore: monthly snapshot archive [skip ci]" || echo "nothing to commit"
          git push

      - name: Alert on success
        if: success()
        uses: dawidd6/action-send-mail@v3
        with:
          server_address: smtp.gmail.com
          server_port: 587
          username: ${{ secrets.ALERT_EMAIL_USER }}
          password: ${{ secrets.ALERT_EMAIL_PASS }}
          to: helena@example.com
          subject: "PM Adaptation Index: pipeline OK (${{ github.run_number }})"
          body: "Daily pipeline completed. Snapshot written."

      - name: Alert on failure
        if: failure()
        uses: dawidd6/action-send-mail@v3
        with:
          server_address: smtp.gmail.com
          server_port: 587
          username: ${{ secrets.ALERT_EMAIL_USER }}
          password: ${{ secrets.ALERT_EMAIL_PASS }}
          to: helena@example.com
          subject: "ALERT: PM Adaptation Index pipeline FAILED"
          body: "Daily pipeline failed. Check GitHub Actions logs immediately."
```

### 5.2 Supabase Keep-Alive (every 3 days)

File: `.github/workflows/keepalive.yml`

```yaml
name: Supabase Keep-Alive

on:
  schedule:
    - cron: '0 12 */3 * *'   # Every 3 days at noon UTC

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping Supabase
        run: |
          curl -sf "${{ secrets.SUPABASE_URL }}/rest/v1/daily_snapshots?select=snapshot_date&limit=1" \
            -H "apikey: ${{ secrets.SUPABASE_ANON_KEY }}" > /dev/null \
            && echo "Supabase alive" || echo "Supabase ping failed"
```

### 5.3 Repository Keep-Alive (monthly -- prevents 60-day inactivity disable)

File: `.github/workflows/repo_keepalive.yml`

```yaml
name: Repository Keep-Alive

on:
  schedule:
    - cron: '0 10 1 * *'    # 1st of every month

jobs:
  keepalive:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - name: Update last-active timestamp
        run: |
          echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .last_active
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .last_active
          git commit -m "chore: monthly keep-alive [skip ci]"
          git push
```

**Required GitHub Secrets:**

| Secret | Description |
|---|---|
| SUPABASE_URL | Supabase project URL |
| SUPABASE_SERVICE_KEY | Service role key (not anon key -- needed for writes) |
| ADZUNA_APP_ID | Adzuna developer app ID |
| ADZUNA_APP_KEY | Adzuna developer app key |
| JSEARCH_API_KEY | RapidAPI key for JSearch |
| ANTHROPIC_API_KEY | Anthropic API key |
| BUTTONDOWN_API_KEY | Buttondown API key |
| ALERT_EMAIL_USER | Gmail address for pipeline alerts |
| ALERT_EMAIL_PASS | Gmail app password for pipeline alerts |

---

## 6. Frontend

### 6.1 Structure

Single React component, no routing. All data fetched from Supabase on load.

```
/frontend
  /src
    App.jsx                  -- root component, fetches data, renders layout
    components/
      Header.jsx             -- title, tagline
      Digest.jsx             -- weekly narrative paragraph (week label + 3-4 sentences)
      HeroMetrics.jsx        -- 3 metrics: PM openings today, new PM jobs today, AI skill rate today
      VolumeChart.jsx        -- Recharts AreaChart: total_postings (daily) + 7-day rolling avg
      AIPenetrationChart.jsx -- Recharts LineChart: ai_penetration_rate (daily) with rolling avg overlay
      SkillsPanel.jsx        -- top 10 AI skills ranked bar list
      CompaniesPanel.jsx     -- top 10 companies with AI skill demand ranked bar list
      RampNotice.jsx         -- days since launch + no-baseline caveat (always visible in MVP)
      Footer.jsx             -- methodology note, data sources, citation, last updated
    lib/
      supabase.js            -- Supabase client initialization (read-only anon key)
```

**Not in MVP (post-launch components, listed here for clarity):**
- `HypothesisBoard.jsx` -- H1/H2 active cards + H3/H4 deferred cards. Added Weeks 7-8. See §10.
- `NarrativeBadge.jsx` -- "Evidence favors: Narrative A / B / Inconclusive." Post-MVP per PRD §6.5.
- `SubscribeCTA.jsx` -- email signup embedded in digest panel. Post-MVP per PRD §6.5.

### 6.2 Data fetching

```javascript
// lib/supabase.js
import { createClient } from '@supabase/supabase-js'
export const supabase = createClient(
  process.env.REACT_APP_SUPABASE_URL,
  process.env.REACT_APP_SUPABASE_ANON_KEY
)

// App.jsx -- fetch on mount
const { data: snapshots } = await supabase
  .from('daily_snapshots')
  .select(`
    snapshot_date,
    data_quality_status,
    total_postings, total_postings_7day_avg,
    new_postings_today, new_postings_7day_avg,
    ai_penetration_rate, ai_penetration_7day_avg,
    top_ai_skills,
    top_employers_ai_skills,
    summary_text,
    digest_generated_at
  `)
  .order('snapshot_date', { ascending: true })
  .limit(365)

// Latest snapshot drives the hero metrics, skills panel, companies panel
const today = snapshots?.at(-1)

// Digest: find the most recent Saturday snapshot with summary_text populated
const latestDigest = snapshots?.filter(s => s.summary_text).at(-1)

// top_ai_skills shape:
// {
//   total_ai_postings_today: 94,
//   skills: [{rank, keyword, count, prev_7day_daily_avg, direction}]
// }
// direction: 'rising' | 'flat' | 'falling' | 'new'
// Render bar width = (count / skills[0].count) * 100% -- scaled to rank 1

// top_employers_ai_skills shape:
// {
//   window_days: 7,
//   window_end: "2026-05-17",
//   companies: [{rank, company, count, prev_count, direction}]
// }
// direction: 'up' | 'flat' | 'down' | 'new'
// Render bar width = (count / companies[0].count) * 100% -- scaled to rank 1

// Ramp notice: days_since_launch is derived in the frontend (no DB column)
const daysSinceLaunch = Math.floor(
  (Date.now() - new Date(snapshots[0].snapshot_date)) / 86_400_000
) + 1

// X-axis "Day N" labels are computed in the frontend:
//   const dayN = (snapshotDate) => Math.floor((snapshotDate - snapshots[0].snapshot_date) / 86_400_000) + 1
```

### 6.3 Chart specs

Both charts must match `design_pai_mvp.html`. Key specs:
- X-axis: "Day N" labels computed from `snapshot_date` (see frontend data section)
- Daily count rendered as a thin dashed line; 7-day rolling average as the prominent solid line
- AI penetration chart Y-axis caps at the max observed rate plus headroom (do not hard-code 100%); a faint dashed reference line at 40% provides scale anchor

**Volume Trend (VolumeChart.jsx):**
```jsx
// chartData: snapshots mapped to include dayLabel (e.g. "Day 1", "Day 42")
<AreaChart data={chartData}>
  <XAxis dataKey="dayLabel" />
  <YAxis />
  <Tooltip />
  <Area type="monotone" dataKey="total_postings_7day_avg"
    stroke="#1a4a7a" fill="url(#volumeFill)" strokeWidth={2.2}
    name="7-day rolling average" />
  <Line type="monotone" dataKey="total_postings"
    stroke="#1a4a7a" strokeOpacity={0.2} strokeDasharray="4 3" strokeWidth={1} dot={false}
    name="Daily count" />
</AreaChart>
```

**AI Penetration Rate (AIPenetrationChart.jsx):**
```jsx
const maxRate = Math.max(...snapshots.map(s => s.ai_penetration_rate ?? 0))
const yMax = Math.ceil((maxRate + 10) / 10) * 10   // round up to next 10

<LineChart data={chartData}>
  <XAxis dataKey="dayLabel" />
  <YAxis tickFormatter={v => `${v}%`} domain={[0, yMax]} />
  <Tooltip formatter={v => `${v.toFixed(1)}%`} />
  <ReferenceLine y={40} stroke="#a06010" strokeDasharray="3 4" strokeOpacity={0.3} />
  <Line type="monotone" dataKey="ai_penetration_rate"
    stroke="#a06010" strokeWidth={2.2} dot={false}
    name="AI requirement rate" />
</LineChart>
```

### 6.4 Environment variables (Vercel)

```
REACT_APP_SUPABASE_URL=https://xxxxx.supabase.co
REACT_APP_SUPABASE_ANON_KEY=eyJhbGc...  (anon/public key -- safe to expose)
```

### 6.5 Supabase Row Level Security

Enable RLS on all tables. Create a single read-only policy for the anon key on `daily_snapshots` only:

```sql
-- Allow public read access to daily_snapshots only
ALTER TABLE daily_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON daily_snapshots
  FOR SELECT USING (true);

-- Raw, enriched, and observability tables: no public access
ALTER TABLE job_postings_raw       ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_postings_enriched  ENABLE ROW LEVEL SECURITY;
ALTER TABLE fetch_log              ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_keywords            ENABLE ROW LEVEL SECURITY;
-- No policies = no access for anon key on these tables
```

---

## 7. File / Repo Structure

```
pm-adaptation-index/
├── .github/
│   └── workflows/
│       ├── daily_pipeline.yml       -- daily 6am PT: fetch → enrich → aggregate → digest(Sat) → backup(Sat)
│       ├── keepalive.yml            -- every 3 days: Supabase ping to prevent 7-day pause
│       └── repo_keepalive.yml       -- 1st of month: commit to prevent 60-day Actions disable
├── pipeline/
│   ├── data/
│   │   ├── ai_keywords.csv
│   │   └── title_normalization.csv
│   ├── scripts/
│   │   ├── fetch.py                 -- daily delta fetch (date_from=yesterday); exits non-zero on source failure
│   │   ├── enrich.py
│   │   ├── aggregate.py             -- daily snapshot computation
│   │   ├── digest.py                -- Saturday-only guard built in
│   │   ├── backup.py                -- dumps daily_snapshots, raw, enriched, fetch_log to JSON
│   │   └── seed_reference_tables.py
│   ├── tests/
│   │   ├── test_fetch.py
│   │   ├── test_enrich.py
│   │   ├── test_aggregate.py
│   │   ├── test_integration.py      -- end-to-end fixture run
│   │   └── test_migration.py
│   ├── fixtures/                    -- canned API responses + fixture postings for integration test
│   └── requirements.txt
├── backups/                         -- monthly snapshot archives committed by daily_pipeline.yml
├── migrations/
│   └── 001_initial_schema.sql
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   └── lib/
│   ├── public/
│   ├── package.json
│   └── .env.local
├── .last_active                     -- updated monthly by repo_keepalive.yml
└── README.md
```

---

## 8. Python Dependencies

```
# pipeline/requirements.txt
supabase==2.x
anthropic==0.x
requests==2.x
python-dateutil==2.x
```

No heavy ML libraries. No pandas required for v1. Keep it lean.

---

## 9. Testing Requirements

### Required before first production run

**test_enrich.py -- critical path tests:**

```python
def test_ai_keyword_match_positive():
    # Description containing "LLM product strategy" should return has_ai_requirement = True
    # ai_keyword_matches should include 'llm'

def test_ai_keyword_match_negative():
    # Description with no AI keywords should return has_ai_requirement = False

def test_ai_keyword_whole_word_only():
    # "calling" should not match "AI" -- whole word boundary required
    # "allocation" should not match "LLM" -- substring match must not fire

def test_title_normalization_senior_pm():
    # "Sr. Product Manager" → normalized_title = "Senior PM", seniority_level = "senior"

def test_title_normalization_director():
    # "Group Product Manager" → normalized_title = "Director", seniority_level = "director"

def test_dedup_hash_deterministic():
    # Same company + title + week always produces same hash

def test_dedup_hash_different_weeks():
    # Same company + title, different week → different hashes
```

**test_aggregate.py:**

```python
def test_dedup_reduces_count():
    # Same company+title appears in both Adzuna and JSearch same window
    # deduplicated count should be less than raw count

def test_ai_penetration_rate_bounds():
    # ai_penetration_rate must be between 0 and 100

def test_rolling_avg_correctness():
    # With 7 days of data [100,110,90,120,105,115,108], rolling avg = 107

def test_top_ai_skills_returns_top_10():
    # Given enriched records with keyword_matches covering 12 distinct keywords:
    #   61 with 'llm', 48 with 'ai product strategy', 31 with 'agentic',
    #   27 with 'prompt engineering', 22 with 'generative ai', 18 with 'ai evaluation',
    #   15 with 'responsible ai', 12 with 'rag', 10 with 'ai platform',
    #   8 with 'foundation model', 4 with 'copilot', 2 with 'nlp'
    # top_ai_skills should have exactly 10 entries
    # rank 1 should be 'llm' with count 61
    # 'copilot' and 'nlp' should not appear (ranks 11 and 12)

def test_top_ai_skills_empty_when_no_ai_records():
    # If no JSearch records today have has_ai_requirement = true
    # top_ai_skills should be [] not None or error

def test_top_ai_skills_direction_rising():
    # Keyword with count 10 today and 7-day avg of 6/day → direction = 'rising'

def test_top_ai_skills_direction_flat():
    # Keyword with count 8 today and 7-day avg of 8/day → direction = 'flat'

def test_top_ai_skills_direction_new():
    # REGRESSION TEST -- previously 0-prev keywords were mislabeled 'rising'.
    # Keyword that has never appeared in any prior enriched record at this
    # pipeline version → direction = 'new' (NOT 'rising')

def test_top_ai_skills_division_uses_actual_days():
    # REGRESSION -- previously divided by 7 even with only 3 days of data.
    # With 3 days of prior data and keyword count [4, 4, 4] (avg 4/day),
    # today's count of 5 → direction = 'flat' (5 / 4 = 1.25 → within 15% threshold).
    # If divided by 7 incorrectly, prev_daily_avg = 12/7 = 1.7, and 5 > 1.95 → 'rising' (wrong).

def test_top_employers_deduplicates_within_window():
    # Same company posting same role (same dedup_hash) on 3 different days
    # within 7-day window should count as 1, not 3

def test_top_employers_dedup_across_week_boundary():
    # REGRESSION -- the old week-bucketed dedup_hash split same role across
    # week boundaries. Same company+title posted last Saturday and Tuesday
    # (within 7-day window but in 2 calendar weeks) must dedupe to 1.

def test_top_employers_returns_top_10():
    # Given 15 companies with AI-skill postings, output has 10 entries
    # rank 1 has the highest count

def test_top_employers_direction_new_takes_precedence():
    # CRITICAL REGRESSION TEST -- the old code had unreachable 'new' branch.
    # Company with prev_count = 0 and current count = 5 must return 'new'
    # (not 'up'). Test fails if 'up' returns instead.

def test_top_employers_direction_ordering():
    # Verify all four directions: prev=0 → 'new', prev=3/curr=5 → 'up',
    # prev=8/curr=3 → 'down', prev=5/curr=5 → 'flat'

def test_top_employers_empty_company_name_excluded():
    # Records where company_normalized = '' should not appear in output

def test_top_employers_uses_jsearch_only():
    # Adzuna records (truncated descriptions) should not contribute --
    # the AI rate is computed from JSearch only

def test_aggregate_idempotent_with_future_rows():
    # REGRESSION -- the old rolling_7day query had no upper bound.
    # Insert snapshots for days 1-10. Reprocess day 5.
    # Day 5's total_postings_7day_avg must equal avg of days 1-4 only,
    # NOT include days 6-10.

def test_ai_penetration_rate_is_daily_not_rolling():
    # ai_penetration_rate must be (today's AI postings / today's total postings) * 100
    # NOT a 7-day rolling rate. The rolling avg lives in ai_penetration_7day_avg.

def test_data_quality_status_partial_when_jsearch_failed():
    # fetch_log for jsearch has status='partial' → snapshot.data_quality_status='partial'
```

**test_integration.py -- end-to-end (required):**

```python
def test_full_pipeline_against_fixture():
    """
    Load 30 fixture job postings (mix of Adzuna/JSearch, mix of AI/non-AI,
    some duplicates, some new companies, some recurring companies) into an
    empty test DB. Run enrich → aggregate. Assert:

    - daily_snapshots row exists for the target date
    - total_postings, ai_penetration_rate, top_ai_skills, top_employers_ai_skills
      all populated
    - top_ai_skills.skills has correct count for the seeded keyword distribution
    - top_employers_ai_skills.companies dedupe correctly across the 7-day window
    - data_quality_status = 'complete' when no fetch_log errors injected

    This is the single highest-value test in the suite -- it catches the
    bug classes that unit tests miss: undefined references, schema/code drift,
    incorrect SQL joins.
    """
```

**test_migration.py:**

```python
def test_migration_runs_on_fresh_db():
    # Apply 001_initial_schema.sql to an empty DB
    # Assert all 5 tables exist: job_postings_raw, job_postings_enriched,
    # daily_snapshots, fetch_log, ai_keywords
    # Assert RLS is enabled where expected
```

### Manual QA checklist (run before launch)

- [ ] Fetch 50 raw records, manually verify title, company, description_text are populated
- [ ] Sample 20 enriched records -- verify AI keyword matches are accurate (not over-matching)
- [ ] Sample 20 records with has_ai_requirement = false -- verify they genuinely lack AI language
- [ ] Verify dedup_rate is between 15-35% (outside this range suggests a bug)
- [ ] Verify daily_snapshots row is written correctly after pipeline run (one row per day, all 4 panel fields populated)
- [ ] Verify fetch_log row written for each source on each run, with correct status
- [ ] Verify data_quality_status = 'complete' on clean runs, 'partial' on simulated source failure
- [ ] Trigger pipeline manually on a weekday -- verify all 4 scripts complete, email alert sent
- [ ] Verify dashboard reads from Supabase and charts render with real data
- [ ] Verify anon key cannot read job_postings_raw, job_postings_enriched, fetch_log, or ai_keywords (RLS check)
- [ ] Verify the "new" badge actually renders for at least one company and one skill during the first 14 days

---

## 10. Extension Points (How Future Features Are Added)

This section documents exactly how each post-MVP feature slots into the existing architecture. Zero schema changes required for most of them.

### Adding a new AI keyword (any time)

1. Insert row into `ai_keywords` table (or update CSV and re-seed)
2. Bump pipeline version: `v1.0` → `v1.1`
3. Run `enrich.py --version v1.1 --since 2026-01-01 --force-reprocess`
4. Run `aggregate.py` to recompute affected daily snapshots
5. The new keyword is now reflected in all historical data

### Adding sector classification (post-MVP)

1. New migration: create `company_sector_lookup` table; add `sector`, `sub_sector`, `sector_source` columns to `job_postings_enriched`; add `sector_breakdown` JSONB column to `daily_snapshots`
2. Build out `sector_lookup.csv` (company → sector mapping)
3. Add enrichment step to `enrich.py` that reads lookup table and populates `sector` and `sub_sector`
4. Bump pipeline version to `v2.0`; reprocess: `enrich.py --version v2.0 --since 2026-01-01`
5. Update `aggregate.py` to populate `sector_breakdown` in `daily_snapshots`
6. Add sector chart to frontend

### Adding requirements trend (post-MVP)

1. New migration: add `skill_keywords` JSONB column to `job_postings_enriched`; add `top_keywords` JSONB column to `daily_snapshots`
2. Add keyword extraction to `enrich.py` that extracts all skill keywords (not just AI) from description_text
3. Update `aggregate.py` to compute `top_keywords`
4. Add requirements trend chart to frontend

### Adding role emergence (post-MVP)

1. New migration: add `is_ai_era_title` boolean to `job_postings_enriched`; add `role_emergence` JSONB to `daily_snapshots`
2. Add AI-era title pattern matching to `enrich.py`
3. Update `aggregate.py` to populate `role_emergence`
4. Add role emergence chart to frontend

### Adding additive/substitutive classification (post-MVP)

1. New migration: add `ai_is_additive` boolean to `job_postings_enriched`; add `additive_rate` to `daily_snapshots`
2. Add logic to `enrich.py`: if `has_ai_requirement = true`, check for traditional PM skill keywords; set `ai_is_additive`
3. Bump to `v3.0`, reprocess
4. Update `aggregate.py` to populate `additive_rate`

### Adding narrative status badge + subscribe CTA (post-MVP)

1. New migration: add `narrative_status` TEXT column to `daily_snapshots`
2. Implement automated narrative status logic in `aggregate.py` (or compute in frontend from accumulated data)
3. Frontend: add `NarrativeBadge.jsx` and `SubscribeCTA.jsx` components

### Adding hypothesis scoreboard (Weeks 7-8)

H1 and H2 status cards are shown on the dashboard with status derived from accumulated data. No new pipeline logic required for the initial implementation — status is computed in the frontend from the snapshots already in `daily_snapshots`.

**Simple frontend status logic (v1 scoreboard):**
```javascript
function computeH2Status(snapshots) {
  if (snapshots.length < 14) return 'accumulating'
  const first = snapshots[0].ai_penetration_rate
  const last = snapshots.at(-1).ai_penetration_rate
  const totalPostingsFirst = snapshots[0].total_postings
  const totalPostingsLast = snapshots.at(-1).total_postings
  const aiGrowth = last - first
  const volumeGrowth = ((totalPostingsLast - totalPostingsFirst) / totalPostingsFirst) * 100
  if (aiGrowth > volumeGrowth + 3) return 'trending_supported'
  if (aiGrowth < volumeGrowth - 3) return 'trending_refuted'
  return 'accumulating'
}
```

When automated status logic is added, store the result in a new `hypothesis_status` JSONB column on `daily_snapshots` (add via migration at that time).

**The pattern is always the same:** enrich → bump version → reprocess → aggregate → add chart. The schema and pipeline structure are designed so this is the only thing that ever changes.

---

## 11. Definition of Done for MVP Launch

The following must all be true before the dashboard goes public:

- [ ] Pipeline has run cleanly for **28 consecutive days** with no manual intervention
- [ ] `daily_snapshots` has 28 rows with non-null `total_postings` and `ai_penetration_rate`
- [ ] `top_ai_skills` is non-null and non-empty on at least 20 of 28 rows
- [ ] `top_employers_ai_skills` is non-null and non-empty on at least 20 of 28 rows
- [ ] Spot-check: manually verify top 10 skills on 3 dates match what keyword matching would produce
- [ ] Spot-check: manually verify top 10 companies on 3 dates are real PM-hiring companies, not junk
- [ ] Spot-check: verify at least one "new" badge appeared correctly during the 28-day window (regression check on the direction-logic bug)
- [ ] Dedup rate is between 15-45%
- [ ] Manual QA of 50 enriched records shows AI keyword matching accuracy > 85%
- [ ] Integration test (test_full_pipeline_against_fixture) passes
- [ ] Migration test (test_migration_runs_on_fresh_db) passes
- [ ] Dashboard is live on Vercel: both charts, skill list, company list, ramp notice all rendering real data
- [ ] Weekly digest email sent successfully on a Saturday referencing skills and companies
- [ ] Failure alert email confirmed working (test by injecting a fake source failure)
- [ ] Supabase keep-alive confirmed running
- [ ] Repository keep-alive confirmed scheduled
- [ ] RLS confirmed: anon key cannot read raw, enriched, fetch_log, or ai_keywords tables
- [ ] Methodology note visible on dashboard noting JSearch-only source for skills and companies, and that AI detection is from job description text not job title

---

*Engineering requirements v1.4. Major review pass against PRD v1.0 and design_pai_mvp.html.*

**Schema:**
- Dropped all forward-looking NULL columns from `job_postings_enriched` (`ai_requirement_type`, `ai_is_additive`, `sector`, `sub_sector`, `sector_source`, `is_ai_era_title`, `role_emergence_cat`) and `daily_snapshots` (`ai_by_type`, `ai_by_seniority`, `sector_breakdown`, `top_keywords`, `role_emergence`, `additive_rate`, `narrative_status`). Each one is added via its own migration when the feature ships.
- Dropped `company_sector_lookup` from MVP migration (added post-MVP with sector module).
- Renamed `daily_snapshots.top_ai_employers` → `top_employers_ai_skills` to match the PRD's "PMs with AI skills" framing.
- Renamed `daily_snapshots.rolling_7day_avg` → `total_postings_7day_avg` for naming consistency with the other 7-day-avg columns.
- Added `daily_snapshots.data_quality_status` + `data_quality_notes` for partial-failure surfacing.
- Added new `fetch_log` table (was referenced by `aggregate.py` but never defined).

**Bug fixes in aggregate.py:**
- Fixed unreachable "new" branch in top-companies direction logic — `prev_count == 0` check now comes first.
- Fixed top-AI-skills direction: added "new" branch (was missing), fixed division-by-actual-days (was always /7), fixed 0-prev edge case.
- Fixed AI penetration rate semantics: now a daily rate (was an average-of-averages). `ai_penetration_7day_avg` is the rolling mean of daily rates.
- Fixed rolling-average idempotency: strict `snapshot_date < target_date` upper bound prevents future rows from being pulled into earlier reprocessed days.
- Removed week-bucketing from `dedup_hash` so company aggregations dedupe correctly across week boundaries within a rolling 7-day window.

**Pipeline observability:**
- `fetch.py` now exits non-zero on source failure (no more silent partials with success email).
- `data_quality_status` propagates through aggregate to surface partial runs in the UI.

**Frontend:**
- Chart JSX rewritten to match design (correct column names, `dayLabel` X-axis, daily-line + rolling-avg overlay, 40% reference line on AI rate, dynamic Y domain).
- Removed dead `NARRATIVE_LABELS` constant (moved post-MVP).
- `HypothesisBoard.jsx`, `NarrativeBadge.jsx`, `SubscribeCTA.jsx` explicitly marked as post-MVP (not in launch component list).
- Ramp notice `days_since_launch` derived from earliest snapshot date (no DB column).

**Backups:**
- Weekly artifact now includes raw, enriched, and fetch_log (not just snapshots).
- Monthly snapshot dump committed to `/backups` in the repo for permanence beyond the 90-day artifact retention.

**Tests:**
- Added regression tests for every bug above (direction-logic, division-by-days, idempotency, dedup across week boundary, AI rate is daily not rolling, data_quality_status propagation).
- Added `test_integration.py` (end-to-end fixture run — highest-value addition) and `test_migration.py` (fresh-DB migration check).*
