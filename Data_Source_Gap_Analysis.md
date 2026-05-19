# Data Source Gap Analysis
## PM Job Market Dashboard — PRD Requirements vs. Candidate Sources
**Reviewed:** May 2026 | **Sources evaluated:** Adzuna, JSearch, TheirStack, LinkUp, Coresignal

---

## Scoring Key

| Score | Meaning |
|---|---|
| ✅ Full coverage | Source meets requirement out of the box |
| ⚠️ Partial | Source meets it partially or with extra engineering work |
| ❌ Not met | Source does not meet this requirement |

---

## Module 1: Market Volume

*PRD requirements: Weekly count of PM postings in the US over 12 months, MoM and YoY comparison, 4-week rolling average, trend line chart.*

| Requirement | Adzuna | JSearch | TheirStack | LinkUp |
|---|---|---|---|---|
| US-scoped PM job counts | ✅ | ✅ | ✅ | ✅ |
| 12-month historical lookback | ✅ (native history endpoint) | ❌ (real-time only) | ⚠️ (available via API, depth unclear) | ✅ (back to 2007) |
| Weekly granularity | ⚠️ (endpoint returns aggregate, may need binning) | ❌ | ⚠️ | ✅ |
| MoM / YoY comparisons | ⚠️ (requires you to store and compute) | ❌ | ⚠️ (requires you to store and compute) | ✅ (built-in analytics) |
| 4-week rolling average | ⚠️ (compute yourself from stored snapshots) | ❌ | ⚠️ | ✅ |

**Module 1 verdict:**
- Adzuna is the only free option with any historical data endpoint. However, it's unclear whether the history endpoint returns weekly vacancy counts broken out by job title (PM-specific) or only aggregate US labor data. This needs to be validated in a spike.
- JSearch is a non-starter for this module — it has no historical data access at all.
- LinkUp is the gold standard here but almost certainly requires enterprise pricing.
- **Critical gap:** No source on the free/cheap tier gives you a ready-made "PM-specific weekly count for the past 12 months" out of the box. You will need to snapshot weekly data yourself from day one and accumulate it. Plan for a 3-month ramp before trend charts look meaningful.

---

## Module 2: Requirements Trend (Skill Keywords)

*PRD requirements: Top 20 skills/tools/keywords per week, YoY trend comparison, rising/falling badges, 2x growth "emerging" tag, sparklines per keyword.*

| Requirement | Adzuna | JSearch | TheirStack | LinkUp |
|---|---|---|---|---|
| Full job description text returned | ⚠️ (description field exists but truncated in some responses) | ✅ (full description text) | ✅ | ✅ |
| Enough volume for keyword frequency analysis | ⚠️ (depends on rate limit) | ✅ (up to 500/query) | ✅ | ✅ |
| Keyword / skill normalization built in | ❌ | ❌ | ⚠️ (title normalization, not skill-level) | ⚠️ |
| Historical keyword trend data | ✅ (salary history endpoint, not keyword-specific) | ❌ | ⚠️ | ✅ |
| Rising/falling/emerging tagging | ❌ (build yourself) | ❌ | ❌ | ❌ |

**Module 2 verdict:**
- All sources require you to build keyword extraction yourself — none return structured skill tags out of the box at the level this module needs.
- JSearch returns the richest full-text descriptions at the highest volume per query, making it the best raw input for NLP/keyword matching. Prioritize JSearch for this module.
- Emerging keyword tagging (2x growth in 6 months) requires your own historical snapshot database regardless of source — you cannot buy this feature.
- **Recommended approach:** Use JSearch to pull 200-500 PM job descriptions weekly, run keyword matching against a curated list of ~100 terms (tools, methodologies, domain tags), store counts in Supabase, compute trends yourself. This is the highest-engineering-effort module in the PRD.

---

## Module 3: Top Employers This Week

*PRD requirements: Top 15 companies hiring PMs this week, ranked by posting count, company logo, posting count, link to listings, company type tag (Startup/Growth/Enterprise/FAANG), delta from last week.*

| Requirement | Adzuna | JSearch | TheirStack | LinkUp |
|---|---|---|---|---|
| Top companies by hiring volume | ✅ (native "top companies" endpoint) | ⚠️ (requires aggregating results yourself) | ✅ (company search with hiring count) | ✅ |
| Link to job listings | ✅ | ✅ | ✅ | ✅ |
| Company logo | ❌ (not in API response) | ❌ | ❌ | ❌ |
| Company type tag (Startup/FAANG/etc.) | ❌ | ❌ | ✅ (funding stage, company size filters) | ❌ |
| WoW delta (up N / down N from last week) | ❌ (build yourself from snapshots) | ❌ | ❌ | ❌ |

**Module 3 verdict:**
- Adzuna's native "top companies" endpoint is the closest thing to a ready-made version of this module — it surfaces company-level vacancy counts without you having to aggregate individual listings. This is Adzuna's biggest advantage for your use case.
- Company logos are not available from any source. You'll need to use the Clearbit Logo API (free for personal use) or similar to enrich company records with logos independently.
- Company type tags (Startup vs. FAANG vs. Enterprise) are only available from TheirStack, which includes funding stage and company size as filter attributes. This is the clearest case for adding TheirStack even at $59/mo.
- WoW delta requires you to store last week's snapshot and compute the diff — no source does this for you.
- **Recommended approach:** Use Adzuna's top companies endpoint as the base feed, enrich with Clearbit for logos, and consider TheirStack to add the company type classification if budget allows.

---

## Module 4: AI-Generated Weekly Digest

*PRD requirements: 2-3 sentence natural language summary generated from structured data, stored with date stamp, powered by Claude API.*

| Requirement | Adzuna | JSearch | TheirStack | LinkUp |
|---|---|---|---|---|
| Structured data payload available to feed Claude | ✅ | ✅ | ✅ | ✅ |
| Sufficient data richness for meaningful summary | ⚠️ (volume + top companies, but no skill trends without separate source) | ⚠️ (current listings only, no employer ranking) | ✅ (combined volume + employer + some enrichment) | ✅ |

**Module 4 verdict:**
- This module is source-agnostic — Claude generates the summary from whatever structured data you pipe in. The quality of the summary depends entirely on how rich the upstream data is.
- Feeding only Adzuna data will produce a summary covering volume and top employers, but not skill trends. Feeding JSearch data alongside adds keyword trends. Combining both sources gives Claude enough to generate a genuinely useful weekly digest.

---

## Non-Functional Requirements Scorecard

| PRD Requirement | Adzuna | JSearch | TheirStack | Notes |
|---|---|---|---|---|
| Weekly automated refresh (GitHub Actions cron) | ✅ | ✅ | ✅ | All support automated API calls |
| Minimal budget (personal project) | ✅ free | ✅ free tier | ⚠️ $59/mo | Adzuna + JSearch = $0 to start |
| US-only geographic filtering | ✅ | ✅ | ✅ | All support country/location filter |
| Deduplication across sources | ❌ (DIY) | ❌ (DIY) | ✅ built-in | TheirStack's deduplication is a real advantage if using multiple sources |
| Title normalization (PM/APM/GPM/TPM taxonomy) | ❌ | ❌ | ⚠️ (partial) | You must build this for all options |
| Historical data from day 1 | ✅ (limited) | ❌ | ⚠️ | Only Adzuna has any historical endpoint |

---

## Summary: Coverage Heatmap

| PRD Module | Adzuna | JSearch | TheirStack | Two-source combo |
|---|---|---|---|---|
| Market Volume Trend | ⚠️ | ❌ | ⚠️ | ⚠️ |
| Skill Requirements Trend | ⚠️ | ✅ | ⚠️ | ✅ |
| Top Employers This Week | ✅ | ⚠️ | ✅ | ✅ |
| AI Digest | ⚠️ | ⚠️ | ✅ | ✅ |
| Budget fit | ✅ | ✅ | ⚠️ | ✅ (free tier) |

---

## Top Gaps Requiring a Decision

### Gap 1: No source gives you 12 months of PM-specific historical volume on day one
**Impact:** High — the entire trend module depends on this. The Adzuna history endpoint exists but needs validation for PM-title specificity. JSearch has nothing. TheirStack's historical depth is unconfirmed for your specific query type.
**Mitigation options:**
- (a) Accept a 3-6 month ramp period where you're accumulating your own snapshots before trend charts become meaningful
- (b) Scope down v1 to "current week" stats only and drop the trend chart to Phase 2
- (c) Pay for LinkUp enterprise access (significant cost, but clean historical data from 2007)

**Recommendation:** Option (a). Commit to running the weekly cron from day one and treat the first 3 months as data accumulation. Show a loading/ramp state in the UI.

### Gap 2: Skill keyword extraction is fully custom-built work for all sources
**Impact:** Medium-high — the requirements trend module is the most technically interesting feature in the PRD but all sources return raw text, not structured skill tags.
**Mitigation options:**
- (a) Curated keyword matching: define a list of ~80-100 PM-relevant terms (Figma, SQL, OKRs, GTM, etc.) and count occurrences per week. Simple, fast, maintainable.
- (b) LLM-based extraction: pass job descriptions to Claude to extract skills as structured JSON. More flexible but costs tokens and has consistency risk.

**Recommendation:** Option (a) for v1. Curated list is more reliable and auditable. Switch to LLM extraction in v2 once you want open-ended skill discovery.

### Gap 3: Company logos not available from any job data source
**Impact:** Low — aesthetic, not functional.
**Mitigation:** Add Clearbit Logo API (free, just point at `logo.clearbit.com/<domain>`). Takes 30 minutes to implement.

### Gap 4: Company type classification (Startup/FAANG/Enterprise) only from TheirStack
**Impact:** Medium — this was called out as a desirable filter in the PRD employers module.
**Mitigation options:**
- (a) Add TheirStack at $59/mo for company enrichment alongside free Adzuna/JSearch
- (b) Hardcode a lookup table for the top 50-100 companies that commonly appear in PM listings
- (c) Deprioritize to Phase 2

**Recommendation:** Option (b) for v1. A manually maintained lookup table of ~100 companies (Google, Meta, Stripe, Salesforce, etc.) covers the vast majority of results that will appear on a "top employers" list. TheirStack adds value if you want this to scale dynamically.

---

## Recommended Architecture Decision

**Use Adzuna + JSearch as the two-source free foundation.** Add TheirStack ($59/mo) only if you want dynamic company type classification and built-in deduplication across sources.

| Source | Role in Pipeline |
|---|---|
| Adzuna | Volume trend data (history endpoint), top employers by week (native endpoint) |
| JSearch | Full job description text for keyword extraction, current listing detail |
| Clearbit Logo | Company logo enrichment (free) |
| TheirStack (optional) | Company type/size classification, cross-source deduplication |

**First spike to run before building anything:**
1. Call `GET api.adzuna.com/v1/api/jobs/us/history?app_id=&app_key=&q=product+manager` and inspect: does it return weekly vacancy counts specific to the PM search query, or only aggregate labor market data?
2. Call JSearch for `"product manager" US` and inspect: how many unique results per query, how complete are description fields, how many duplicates appear?
3. Validate that combining the two sources doesn't require prohibitive deduplication effort.

Results of this 2-hour spike should confirm or change the source recommendation before any further architecture work.
