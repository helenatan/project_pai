# PM Adaptation Index

An empirical observatory tracking how AI is reshaping the product management profession.

## What it is

A daily data pipeline that pulls PM job postings from Adzuna and JSearch, detects AI skill requirements via keyword matching, and surfaces the signal on a public dashboard updated every morning at 6am PT.

## Architecture

```
[Adzuna API] ─┐
               ├─► fetch.py ─► job_postings_raw ─► enrich.py ─► job_postings_enriched ─► aggregate.py ─► daily_snapshots ─► React Dashboard
[JSearch API] ─┘                                                                                      │
                                                                                          digest.py (Saturdays) ─► Buttondown email
```

Pipeline runs as GitHub Actions cron jobs. No backend server. Frontend reads from Supabase via the public anon key.

## Getting started

### 1. Set up Supabase

1. Create a new project at [supabase.com](https://supabase.com)
2. Run [migrations/001_initial_schema.sql](migrations/001_initial_schema.sql) in the SQL editor
3. Seed the AI keywords: set env vars and run `python pipeline/scripts/seed_reference_tables.py`

### 2. Configure GitHub Secrets

Add these secrets to your GitHub repo (Settings → Secrets → Actions):

| Secret | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Service role key (for pipeline writes) |
| `SUPABASE_ANON_KEY` | Anon key (for keep-alive ping) |
| `ADZUNA_APP_ID` | Adzuna developer app ID |
| `ADZUNA_APP_KEY` | Adzuna developer app key |
| `JSEARCH_API_KEY` | RapidAPI key for JSearch |
| `ANTHROPIC_API_KEY` | Anthropic API key (digest generation) |
| `BUTTONDOWN_API_KEY` | Buttondown API key (email send) |
| `ALERT_EMAIL_USER` | Gmail address for pipeline alerts |
| `ALERT_EMAIL_PASS` | Gmail app password for alerts |

### 3. Deploy the frontend

1. Copy `frontend/.env.local` and fill in your Supabase URL and anon key
2. Deploy to Vercel: connect your GitHub repo, set the root directory to `frontend/`, add the two env vars in Vercel's dashboard

### 4. Trigger a test run

Go to Actions → Daily Pipeline → Run workflow.

## Running pipeline scripts locally

```bash
cd /path/to/pm-adaptation-index
pip install -r pipeline/requirements.txt

export SUPABASE_URL=...
export SUPABASE_SERVICE_KEY=...
export ADZUNA_APP_ID=...
export ADZUNA_APP_KEY=...
export JSEARCH_API_KEY=...

python pipeline/scripts/fetch.py
python pipeline/scripts/enrich.py --version v1.0
python pipeline/scripts/aggregate.py
```

## Running tests

Unit tests (no network needed):

```bash
pip install pytest
pytest pipeline/tests/test_enrich.py pipeline/tests/test_aggregate.py pipeline/tests/test_fetch.py -v
```

Integration + migration tests (requires a test Supabase project):

```bash
export TEST_SUPABASE_URL=...
export TEST_SUPABASE_SERVICE_KEY=...
pytest pipeline/tests/ -v
```

## Definition of done for public launch

See [erd_pai_v1.md](erd_pai_v1.md) §11 for the full pre-launch checklist. The short version: 28 consecutive days of clean pipeline runs, all QA checks passed, integration test green.

## Adding a new AI keyword

1. Add a row to `ai_keywords` in Supabase (or update `pipeline/data/ai_keywords.csv` and re-seed)
2. Bump the pipeline version: `v1.0` → `v1.1`
3. Reprocess: `python pipeline/scripts/enrich.py --version v1.1 --since 2026-01-01 --force-reprocess`
4. Recompute snapshots: `python pipeline/scripts/aggregate.py`
