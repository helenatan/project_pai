# Implementation Feasibility Assessment
## The PM Adaptation Index — v1 Engineering Review

**Status:** v1.0
**Reviewer:** Staff Engineer perspective
**Date:** May 2026
**Scope:** Week 0-6 launch requirements against actual API and infrastructure constraints

---

## Executive Summary

The v1 architecture is sound. The pipeline design, schema decisions, and infrastructure choices are all defensible. However, there is one critical blocker and four significant risks that require resolution before any code is written. The critical blocker -- the Adzuna history endpoint returning salary data, not vacancy counts -- changes the entire approach to H1 (the volume trend hypothesis) and needs an immediate spike. If unresolved, the project ships without a pre-AI baseline and the central thesis cannot be tested.

**Overall feasibility: High -- with one architectural change required.**

---

## Component-by-Component Assessment

---

### 1. Adzuna API

**Verdict: PARTIAL FIT — critical gap on historical endpoint**

**What is confirmed working:**

The Adzuna API consists of nine endpoints covering search, employment data, historical data, salary data, and top companies. The search endpoint (`/jobs/us/search/{page}`) works as documented and supports `what=product+manager` keyword filtering with US country targeting. The top companies endpoint returns a leaderboard of top employers by vacancy count filtered by keyword and location -- directly useful for Month 4 features. These are confirmed from live documentation.

**The critical problem with the history endpoint:**

The Adzuna history endpoint returns salary and vacancy data. The documented response structure returns a `month` object with monthly salary averages keyed by YYYY-MM.

This is the blocker. The history endpoint returns **salary averages over time**, not **vacancy counts over time**. The PRD and engineering doc assume this endpoint returns monthly PM job posting volume -- the pre-AI baseline that H1 depends on. It does not. The response is average salary by month, not count of job postings by month.

The `top_companies` endpoint returns the current number of vacancies per employer but has no time dimension -- it is always current, never historical.

**What this means for the project:**

There is no free Adzuna API endpoint that returns historical vacancy counts broken out by job title keyword over time. The pre-AI baseline (2021-2022 PM posting volume) cannot be constructed from Adzuna's free API as currently documented.

**Mitigation options (in order of preference):**

- **Option A (recommended):** Scrap the pre-AI baseline for v1. Launch with "from tracking start" as the x-axis origin. Be explicit in the methodology note that the pre-AI comparison requires 12+ months of accumulated data. The volume trend chart still works -- it just starts from launch week, not 2021. H1 becomes a 12-month question rather than a day-one finding. This is honest and survivable.

- **Option B:** Contact Adzuna directly to ask whether their premium data offering (mentioned on the developer page: "we can provide much more: historical data") includes vacancy counts by keyword over time. This requires a sales conversation and likely costs money.

- **Option C:** Use the `count` field from the search endpoint (`/jobs/us/search/1?what=product+manager`) -- this returns total matching results. Make one API call per week, store the count, and build the historical baseline manually. This works but means week 1 is the earliest data point. Still no 2021 baseline.

**Option A is the right call for v1.** Document it honestly and move on.

**Rate limits and pagination:**

The Adzuna API free tier enforces rate limits of 25 requests per minute and 250 requests per day. This is the actual confirmed rate limit from a developer project. The engineering doc assumes "1 request per second" which aligns with the 25/min ceiling. 250 requests per day is the binding constraint for pagination.

For a weekly batch fetch of PM listings in the US: paginating through results at 50 per page means roughly 80-100 pages to capture ~4,000-5,000 postings. At 50 results per page that is 80-100 requests. With a 250/day limit, a single weekly fetch comfortably fits within the limit if batched carefully. **This is fine for v1.**

**Description field:**

The Adzuna search API documentation explicitly notes "we currently only provide a snipped of the job description in the response." This is a confirmed limitation. The `description` field returns a truncated excerpt, not the full job description. This directly impacts the AI keyword extraction module -- matching AI keywords against a truncated description will produce false negatives (postings that mention AI but only in the body text that was cut off).

**Impact on AI signal module:** Moderate-to-high false negative rate from Adzuna descriptions. The AI penetration rate computed from Adzuna data alone will be an undercount. JSearch becomes the primary source for keyword extraction for this reason.

---

### 2. JSearch API (RapidAPI)

**Verdict: FIT -- with rate limit arithmetic that needs verification**

**Coverage and data quality:**

JSearch aggregates job postings from LinkedIn, Indeed, Glassdoor, ZipRecruiter, Monster, and Google for Jobs. Each job posting includes over 40 data points including job title, full job description, required experience, education, skills, and job location.

Full job description text is confirmed -- this is the key advantage over Adzuna for keyword extraction.

JSearch returns up to 500 job listing results per query. The API response time is between 1 and 8 seconds depending on the endpoint and parameters.

**Rate limits -- the real numbers:**

The most specific criticism of JSearch involves pagination confusion -- a documentation issue where `num_pages` and `page` parameters can produce repeating jobs across pages, and the docs are not clear on how to get maximum results without duplicates.

The free tier on RapidAPI for JSearch is confirmed to be very limited. Based on current RapidAPI marketplace structure, the free tier for JSearch is approximately **10 requests per month** -- not 500 or 1,000. The engineering doc assumes `num_pages=5` in a single weekly call, which would use 5 of those 10 monthly requests just for the weekly fetch. That leaves nothing for testing, debugging, or failed retry attempts.

**This is a significant budget constraint for v1.** At 10 free requests per month, the JSearch integration is feasible only if the project pays for a basic plan. RapidAPI paid tiers typically start at $15/month for 50,000 requests -- the basic JSearch plan is in this range and entirely affordable for a personal project. This should be budgeted from the start.

**Pagination duplication bug:**

The known pagination issue where repeated calls with incrementing `page` parameters return duplicate results is a real data quality concern. The dedup strategy in the engineering doc (hash on `source_id`) handles this correctly -- any duplicate `job_id` from JSearch is caught by the unique constraint on `(source, source_id)`. The dedup architecture is correct. Just be aware the raw `total_postings_raw` count will be inflated before dedup runs.

**Response time:**

At 1-8 seconds per request and 5 pages per weekly fetch, the JSearch fetch step could take up to 40 seconds. This is within the 30-minute GitHub Actions timeout with substantial margin.

---

### 3. Supabase (Database)

**Verdict: FIT -- with one critical operational risk**

**Free tier limits confirmed:**

The Supabase free plan in 2026 includes 500 MB database storage, 50,000 monthly active users, and 200 concurrent realtime connections.

**Storage math for v1:**

The raw storage concern is real. Each `job_postings_raw` row stores the complete API response as JSONB (`raw_payload`). A typical job listing JSON object from Adzuna or JSearch is approximately 3-8 KB including full description text. At 5,000 deduplicated postings per week and 52 weeks per year, that is 260,000 raw records. At an average of 5 KB per record, raw storage alone is 1.3 GB -- well over the 500 MB free tier limit within 6-9 months.

**Mitigation:** Do not store the full `raw_payload` for every record indefinitely. Store it for 90 days, then drop the JSONB column (keep the structured fields). Alternatively, store `raw_payload` only for a sample (1 in 10 records) after month 3. The structured columns (`title`, `company`, `description_text`, etc.) are what matter for analytics.

**The 7-day inactivity pause is the real risk:**

Supabase free projects are automatically paused after 7 days of no activity. Resuming is easy but if a user tries to access the app during a pause window, they get an error.

The weekly cron job writes to Supabase every Saturday. If the GitHub Actions cron misses a week (which happens -- see GitHub Actions section below), Supabase will not receive a write for 7+ days and the project gets paused. The dashboard then returns errors until someone manually resumes it.

**Fix:** Add a keep-alive ping to the GitHub Actions workflow that runs every 3 days (separately from the weekly pipeline) to prevent the 7-day pause. This is a 5-line workflow file and is essential for a publicly facing dashboard.

Free plan projects enter read-only mode when database size exceeds 500 MB.

**Recommendation:** Budget for Supabase Pro ($25/month) from Month 3 onward. The free tier is sufficient for the 6-week v1 build period but will hit storage limits within 6-9 months at full data volume.

**No automatic backups on free tier:**

There are no automatic backups on the free plan. The 500 MB limit is not the biggest risk -- the lack of backups is.

Set up a weekly Postgres dump to GitHub artifacts or an S3-compatible storage from day one. Losing 3 months of accumulated job data because of an accidental truncate or a corrupted migration would be devastating. This is a 20-line addition to the GitHub Actions workflow.

---

### 4. GitHub Actions (Pipeline Orchestration)

**Verdict: FIT -- with one repo visibility decision required**

**Free tier for public vs. private:**

For public repositories, standard GitHub-hosted runners and self-hosted runners are free and unlimited. Private repositories have a free limit of 2,000 minutes per month.

The weekly pipeline runs once a week. At an estimated 5-10 minutes per run, that is ~40-80 minutes per month for a private repo -- well within the 2,000 minute free tier. **The private repo choice is fine from a cost perspective.**

**The cron reliability problem:**

Scheduled workflows do not run at the exact time specified. During periods of high demand on GitHub Actions, delays of 10-30 minutes are common. Delays of over an hour have been reported during peak usage. GitHub does not guarantee execution timing.

For a weekly Saturday batch this is acceptable -- a 1-hour delay on a weekly job is noise, not a problem.

More serious: if a repository has no commits, pull requests, or issues for 60 consecutive days, GitHub automatically disables all scheduled workflows. You will receive an email notification but if you miss it, your scheduled tasks stop running silently.

This is a real operational risk. A pipeline that silently stops after 60 days of no commits will kill the project without any obvious warning. **Fix:** Add a `workflow_dispatch` trigger with a monthly no-op commit, or configure a lightweight GitHub bot to make a scheduled commit (update a `last_run.txt` file).

**The engineering doc already has `workflow_dispatch` in the workflow spec** -- this is good. But the 60-day inactivity disable is not currently mitigated.

---

### 5. Buttondown (Email)

**Verdict: FIT**

The Buttondown API is simple and well-documented. Free tier supports up to 1,000 subscribers, which covers the entire v1 period. The API call in the engineering doc (`POST /v1/emails` with `status: "about_to_send"`) is correct. No issues here.

One note: Buttondown sends emails from a `@buttondown.email` domain unless you configure a custom sending domain. For a project with credibility aspirations in the PM community, setting up a custom sending domain (`digest@pmadaptationindex.com` or similar) is worth the 30 minutes of setup time.

---

### 6. Anthropic API (Digest Generation)

**Verdict: FIT**

The Claude API call in the engineering doc is correctly specified. `claude-sonnet-4-20250514` is the right model. `max_tokens=300` is appropriate for a 3-4 sentence digest. One run per week at roughly $0.003-0.005 per call is negligible cost.

One improvement to the system prompt: add explicit instruction to never reference specific numbers without the unit (e.g., always write "4,312 postings" not "4,312"). The current prompt does not specify this and Claude may occasionally drop units when generating tightly constrained text.

---

### 7. React + Recharts Frontend

**Verdict: FIT**

The frontend spec is straightforward and correctly scoped. Recharts is the right choice -- well-maintained, sufficient for two simple charts. The single-page no-routing architecture is appropriate for v1.

One note: the chart specs in the engineering doc use `preserveAspectRatio="none"` on SVG elements, which the HTML mock does correctly. However, the Recharts `<AreaChart>` and `<LineChart>` components handle their own SVG -- do not pass `preserveAspectRatio` to Recharts components directly. The mock is HTML/SVG; the actual React implementation will use Recharts API which is different. This is a minor but real gotcha during implementation.

The Supabase anon key exposure in the frontend is fine given the RLS configuration documented in the engineering spec. Confirm RLS is configured before deploying.

---

## Summary Risk Matrix

| Risk | Severity | Likelihood | Status |
|---|---|---|---|
| Adzuna history endpoint returns salary not vacancy counts | Critical | Confirmed | Needs architectural decision before build |
| Adzuna description field is truncated | High | Confirmed | Mitigated: use JSearch as primary for keyword extraction |
| JSearch free tier too limited (10 req/month) | High | Very likely | Budget $15/month for basic plan from day one |
| Supabase 7-day inactivity pause | High | Medium | Add keep-alive cron, document recovery steps |
| Supabase 500 MB storage hit within 6-9 months | High | Likely | Plan raw_payload TTL strategy before month 3 |
| No Supabase backups on free tier | High | Always true | Add weekly pg_dump to GitHub artifacts from day one |
| GitHub Actions 60-day inactivity disable | Medium | Low | Add monthly no-op commit or keep-alive mechanism |
| GitHub Actions cron delay (up to 1 hour) | Low | Medium | Acceptable for weekly batch |
| JSearch pagination duplication | Low | Confirmed | Mitigated by existing dedup hash strategy |
| Buttondown sending domain looks unprofessional | Low | Always true | Set up custom sending domain before launch |

---

## Required Changes to the Engineering Doc Before Building

### Change 1: Remove the pre-AI baseline assumption (Critical)

The engineering doc specifies `% change vs. the pre-AI baseline (defined as average weekly postings in 2021)`. This baseline cannot be retrieved from Adzuna's free API. The history endpoint returns salary averages, not vacancy counts.

**Replace with:** The volume trend chart starts from tracking launch week. The methodology note explicitly states: "Historical data before tracking start is not available from our data sources at no cost. The pre-AI comparison will be constructed from our own accumulated data after 12 months of continuous tracking."

The aggregate script's baseline calculation should use the rolling average of the first 4 weeks of data as the initial reference point rather than referencing an undefined 2021 value.

### Change 2: Hardcode JSearch to paid tier from day one (High)

The engineering doc lists JSearch as "Free tier" in the data sources table. Given the ~10 request/month free tier limit, the fetch script as written (`num_pages=5` per weekly run = 5 requests per run) will exhaust the monthly allowance in two runs. Update the data sources table to reflect $15/month JSearch Basic plan.

### Change 3: Add Supabase keep-alive workflow (High)

Add a second GitHub Actions workflow file:

```yaml
name: Supabase Keep-Alive
on:
  schedule:
    - cron: '0 12 */3 * *'  # Every 3 days at noon UTC
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping Supabase
        run: |
          curl -s "${{ secrets.SUPABASE_URL }}/rest/v1/weekly_snapshots?select=week_start_date&limit=1" \
            -H "apikey: ${{ secrets.SUPABASE_ANON_KEY }}" > /dev/null
```

This single read query every 3 days prevents the 7-day inactivity pause without touching any data.

### Change 4: Add weekly database backup (High)

Add a backup step to the weekly pipeline that dumps the weekly_snapshots table to a GitHub artifact:

```yaml
- name: Backup weekly snapshots
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}  # Add this secret
  run: |
    pip install psycopg2-binary
    python -c "
    import psycopg2, json, os
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute('SELECT * FROM weekly_snapshots ORDER BY week_start_date')
    rows = cur.fetchall()
    with open('backup_snapshots.json', 'w') as f:
        json.dump([list(r) for r in rows], f, default=str)
    "
  continue-on-error: true  # Don't fail the pipeline if backup fails

- name: Upload backup artifact
  uses: actions/upload-artifact@v4
  with:
    name: weekly-snapshots-backup-${{ github.run_number }}
    path: backup_snapshots.json
    retention-days: 90
```

### Change 5: Add Adzuna description truncation to methodology note (Medium)

Add to the methodology note: "The Adzuna API returns truncated job descriptions. AI keyword matching against Adzuna data will produce a lower AI penetration rate than JSearch data for the same time period due to this truncation. The reported rate uses JSearch as the primary source for keyword extraction."

### Change 6: Update dedup rate sanity check (Minor)

The engineering doc specifies "dedup_rate is between 15-35% (sanity check)." Given the JSearch pagination duplication issue, the raw dedup rate may be higher -- 30-50% is a more realistic range when JSearch pagination is returning overlapping results. Adjust the sanity check thresholds accordingly to avoid false alarm pages.

---

## Week 0 Spike Protocol (Updated)

Before writing any pipeline code, the following two spikes must be completed and their results documented.

**Spike 1: Confirm Adzuna search count (1 hour)**

Make a single authenticated GET call to:
```
https://api.adzuna.com/v1/api/jobs/us/search/1
  ?app_id=YOUR_ID&app_key=YOUR_KEY
  &what=product+manager
  &results_per_page=1
  &content-type=application/json
```
Inspect the response for a `count` field. If present, this is the total number of PM listings in the US at that moment. Record this number. Make the same call the following Saturday. The week-over-week difference in `count` is the volume trend metric. If the `count` field exists and is stable, the volume trend module works without the history endpoint.

**Spike 2: Confirm JSearch description field completeness (1 hour)**

On the JSearch free tier (10 free requests -- use them carefully), make one call:
```
GET https://jsearch.p.rapidapi.com/search
  ?query=product+manager+in+united+states
  &page=1&num_pages=1
Headers: X-RapidAPI-Key: YOUR_KEY
```
Inspect the first 5 results. Check:
- Is `job_description` present and untruncated?
- Are any AI-related keywords visible in the description text of relevant roles?
- What is the average character length of `job_description`?

If descriptions are full-text and keyword-searchable, JSearch is confirmed as the AI signal source. If they are also truncated, escalate to a paid API source evaluation.

**Spike results must be documented before any pipeline code is written.** These two spikes are the technical equivalent of Phase 0 hypothesis definition -- they validate the assumptions the entire architecture rests on.

---

## Budget Estimate (v1, First 6 Months)

| Item | Monthly Cost | Notes |
|---|---|---|
| Supabase Free | $0 | Sufficient for 6 weeks; plan upgrade by Month 3 |
| Supabase Pro (Month 3+) | $25 | 8 GB storage, no pausing, backups |
| Adzuna API | $0 | Free tier, 250 req/day sufficient |
| JSearch Basic | $15 | Required -- free tier is 10 req/month |
| GitHub Actions | $0 | Public repo: unlimited; private repo: well within 2,000 min/month |
| Anthropic API | ~$1 | 52 digest generations/year at ~$0.005/call |
| Buttondown | $0 | Free up to 1,000 subscribers |
| Vercel | $0 | Free tier for static frontend |
| Custom domain (optional) | ~$12/year | For pmadaptationindex.com |
| **Total v1 (months 1-2)** | **~$16/month** | |
| **Total v1 (months 3-6)** | **~$41/month** | After Supabase upgrade |

---

*Feasibility assessment v1.0. One critical architectural change required (remove pre-AI baseline assumption for Adzuna history endpoint). All other components are feasible with the mitigations documented above. Recommended next step: run the two Week 0 spikes before writing any pipeline code.*
