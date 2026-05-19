# PRD: The PM Adaptation Index
### An Empirical Observatory for How AI is Reshaping the Product Management Profession

**Status:** Draft v1.0
**Author:** Helena
**Last Updated:** May 2026
**Project Type:** Personal / Community / Research

---

## 1. The Thesis

Two credible but contradictory narratives exist about AI and the job market right now.

**Narrative A:** AI is eliminating knowledge work at scale. PM roles will be automated away. In five years, companies will need a fraction of the product managers they employ today.

**Narrative B:** AI is a productivity multiplier. Demand for PMs who can work with AI systems is higher than ever. Job postings are at record levels.

Both narratives are stated with confidence. Neither is grounded in systematic, longitudinal evidence. Most people are navigating a once-in-a-generation labor market shift using anecdote, LinkedIn feed anxiety, and vibes.

**The central question this project exists to answer:**

*Is AI eliminating PM roles, transforming them, or creating new ones -- and what does the empirical evidence actually show, week by week, over time?*

The biggest advantage humans have in any paradigm shift is adaptability. But adaptation requires signal. This project builds that signal for the PM community -- starting with data, updated continuously, with no agenda other than finding out what is true.

---

## 2. Vision

The PM Adaptation Index is a publicly shareable, empirically grounded web dashboard that tracks how AI is reshaping product management demand in the United States. It is not a job board. It is not a career coaching tool. It is an observatory.

It starts with the PM community. The methodology is designed to extend to other knowledge worker disciplines over time.

**Four questions the MVP dashboard answers:**

1. **Volume:** Is total PM hiring growing, flat, or contracting since AI went mainstream?
2. **AI Signal:** How rapidly are AI-fluency requirements appearing in PM job descriptions?
3. **AI Skills:** Which specific AI skills are appearing most frequently in PM job descriptions right now?
4. **Companies:** Which companies are most actively seeking PMs with AI skills in their job descriptions?

Everything else -- sector breakdown, role emergence, requirements trend, seniority analysis -- is post-launch, earned by community demand and data maturity.

---

## 3. Target Users

**Primary:** Product managers at every career stage -- from PMs just entering the field to senior leaders and CPOs. Everyone is navigating the same uncertainty about what AI means for their career and their team. They need honest signal, not reassurance. Trend data, not point-in-time snapshots.

**Secondary:** PM community builders, newsletter writers, and educators who need credible, citable data. They are the amplifiers. When the data says something counterintuitive, they share it.

**Tertiary:** Helena -- building in public, using her PM community as the initial distribution channel.

**The community's role:** Co-authors of the inquiry, not passive consumers. The pre-launch hypothesis poll, the weekly qualitative prompt, and the eventual hypothesis submission mechanism are all designed to deepen that co-authorship.

---

## 4. Hypotheses

Two hypotheses at launch. Others deferred until MVP data is mature enough to test them meaningfully.

| # | Hypothesis | Status | Tests With |
|---|---|---|---|
| H1 | PM hiring is in structural decline during the tracking period | Determined by accumulated data | Volume Trend |
| H2 | AI requirements are growing faster than total PM posting volume | Determined by accumulated data | AI Signal |

Hypothesis status is not pre-determined. Each hypothesis starts with no verdict and transitions to a directional status (accumulating signal, trending supported, trending refuted) only as real data accumulates from Day 1 of the project. There is no historical data before the pipeline first runs.

**Deferred hypotheses (when data matures):**

| # | Hypothesis | Requires |
|---|---|---|
| H3 | New PM titles (AI PM, Agentic PM) are appearing and accelerating | Sufficient weeks of title data to show emergence curves |
| H4 | Traditional PM skills are declining as a share of job descriptions | Requirements Trend module |
| H5 | AI-native sectors require AI skills earlier than legacy sectors | Sector module |
| H6 | PM roles that survive require human judgment at the AI boundary | Role Emergence + Requirements modules |

---

## 5. Goals and Non-Goals

### Goals

- Build a reliable daily data pipeline that accumulates PM job market signal continuously
- Track total PM posting volume and AI penetration rate as the two primary metrics
- Surface the top AI skills and top companies by AI skill demand in each daily snapshot
- Publish a weekly digest that interprets the signal against the central thesis
- Build community trust through intellectual honesty -- including when data is inconclusive
- Establish a public methodology that can be cited and scrutinized
- Keep the project running reliably on a personal budget for 12+ months

### Non-Goals for the MVP (first 3 months)

- Sector or sub-sector breakdown
- Role emergence tracking
- Requirements trend module
- Seniority analysis
- Additive vs. substitutive AI classification
- Community hypothesis submission forms
- Resume matching, salary data, geographic breakdown
- Dark mode, mobile optimization beyond basic responsiveness
- Automated hypothesis status classification

---

## 6. Feature Scope

### What ships at MVP launch

**Five things.**

#### 6.0 Hero Metrics Bar

Three summary metrics displayed together above the charts, giving an at-a-glance read of today's state before the reader reaches the trend lines.

| Metric | Source | Delta shown |
|---|---|---|
| PM openings in the US today | Adzuna live count | % change vs. 7-day rolling avg |
| New PM jobs posted today | Adzuna daily new postings | % change vs. 7-day rolling avg |
| Jobs requiring AI skills today | AI keyword match rate | Points change vs. 7-day rolling avg |

#### 6.1 Volume Trend Chart

A single area chart showing daily PM job posting count in the US over time, with a 7-day rolling average overlaid. This directly tests H1.

- X-axis: days since tracking began
- Y-axis: total active PM postings (Adzuna live count)
- Primary line: 7-day rolling average
- Secondary: daily raw count (lighter)

#### 6.2 AI Penetration Rate Chart

A single line chart showing what percentage of PM job postings mention any AI-related requirement, trended over time. This directly tests H2.

- X-axis: days since tracking began
- Y-axis: % of postings with AI keyword match (7-day rolling window)
- Hero callout: current rate + points change vs. 7-day rolling avg

**AI keyword list (40 terms, stored in DB, not hardcoded):**
LLM, large language model, generative AI, GenAI, gen AI, agentic, AI agent, prompt engineering, RAG, retrieval augmented, fine-tuning, AI evaluation, responsible AI, AI safety, foundation model, multimodal, copilot, AI-native, machine learning product, ML product, artificial intelligence product, AI product manager, AI product strategy, AI roadmap, AI features, conversational AI, natural language processing, NLP product, AI platform, model evaluation, AI governance, AI ethics product, AI integration, AI tooling, AI workflow, AI-powered, LLM-powered, agent-based, agentic workflow, AI-first

#### 6.3 Top 10 AI Skills Today

A ranked list of the ten most frequently mentioned AI-related keywords across all PM job postings captured today, sourced from JSearch full-text descriptions. **Job opening count is the primary data point** -- it tells you how many postings today mentioned each skill in the job description or requirements, which is the signal that makes the ranking meaningful.

**What it shows:**
- Rank 1-10: keyword label + **job opening count** (number of today's postings mentioning this keyword in the full job description)
- Proportional bar: a horizontal fill bar scaled to the top keyword's count, so relative magnitude is visible at a glance
- Direction badge: rising / flat / falling vs. the prior 7-day daily average
- Subheading: total number of AI-positive postings today and the share of all PM postings they represent (denominator context)
- Updated daily alongside the rest of the pipeline

**Why count is the primary signal, not percentage:** Percentage of postings mentioning a skill fluctuates based on sample size. On a day where only 40 postings came in, 50% sounds significant but is 20 jobs. On a day with 200 postings, 30% is 60 jobs -- triple the real demand. The raw count anchors the reader to actual hiring signal.

**Note on data source:** The skills list is derived from full-text job description analysis via JSearch. The subheading on the UI panel does not need to label the source explicitly -- the methodology note in the footer covers this. What matters is that the subheading gives the denominator context (how many total AI-positive postings today, and what share of all PM openings that represents).

**Data format in JSONB:**
```json
{
  "total_ai_postings_today": 94,
  "skills": [
    { "rank":  1, "keyword": "LLM / large language model",      "count": 61, "direction": "rising"  },
    { "rank":  2, "keyword": "AI product strategy",             "count": 48, "direction": "flat"    },
    { "rank":  3, "keyword": "Agentic / AI agent",              "count": 31, "direction": "rising"  },
    { "rank":  4, "keyword": "Prompt engineering",              "count": 27, "direction": "flat"    },
    { "rank":  5, "keyword": "Generative AI / GenAI",           "count": 22, "direction": "falling" },
    { "rank":  6, "keyword": "AI evaluation / evals",           "count": 18, "direction": "rising"  },
    { "rank":  7, "keyword": "Responsible AI / AI safety",      "count": 15, "direction": "flat"    },
    { "rank":  8, "keyword": "RAG / retrieval augmented",       "count": 12, "direction": "rising"  },
    { "rank":  9, "keyword": "AI platform / AI tooling",        "count": 10, "direction": "flat"    },
    { "rank": 10, "keyword": "Foundation model / multimodal",   "count":  8, "direction": "new"     }
  ]
}
```

**Display format:**
```
Top AI Skills Today
1,472 postings mention AI skills (34.1% of all PM openings)

 1. LLM / large language model      ████████████████████████  61 jobs  ▲
 2. AI product strategy             ███████████████████       48 jobs  ▸
 3. Agentic / AI agent              █████████████             31 jobs  ▲
 4. Prompt engineering              ███████████               27 jobs  ▸
 5. Generative AI / GenAI           █████████                 22 jobs  ▾
 6. AI evaluation / evals           ███████                   18 jobs  ▲
 7. Responsible AI / AI safety      ██████                    15 jobs  ▸
 8. RAG / retrieval augmented       █████                     12 jobs  ▲
 9. AI platform / AI tooling        ████                      10 jobs  ▸
10. Foundation model / multimodal   ███                        8 jobs  ★
```

#### 6.4 Top 10 Companies Hiring PMs with AI Skills

A ranked list of the ten companies with the most open PM job postings that mention AI-related skills in the job description or requirements, sourced from JSearch full-text descriptions over a 7-day rolling window. **Qualification is based on job description text, not job title** -- a posting counts when the full description matches any term from the AI keyword list, regardless of what the role is called. **Job opening count is the primary data point** -- it directly answers which companies are generating the most demand for PMs with AI skills right now.

**What it shows:**
- Rank 1-10: company name + **job opening count** (distinct deduplicated postings in the past 7 days where the description mentions AI skills)
- Proportional bar: horizontal fill bar scaled to rank 1's count, so the gap between companies is immediately visible
- Direction badge: up / flat / down / new vs. the prior 7-day window
- Subheading: window context ("7-day rolling window ending today")
- Updated daily

**Data extraction note:** A posting titled "Senior Product Manager" qualifies if its description mentions LLM, prompt engineering, agentic workflows, or any other term from the AI keyword list. A posting titled "AI PM" does not qualify if its description contains no AI-related language. This grounds the signal in actual requirements, not aspirational titling.

**Why a 7-day rolling window:** A single day's company-level data is too sparse -- a company posting 3 roles on one Tuesday looks like a top employer when it might be a one-time burst. The 7-day window reflects sustained hiring activity. The count always answers: how many distinct PM roles with AI skill requirements has this company posted in the past 7 days.

**Note on data source:** Company data comes from JSearch full-text descriptions. As with the skills panel, the source does not need to be labeled explicitly in the panel subheading -- the footer methodology note covers sourcing. The subheading should convey the window ("7-day rolling window") so readers understand they are not looking at a single day's snapshot.

**Data format in JSONB:**
```json
{
  "window_days": 7,
  "window_end": "2026-05-17",
  "companies": [
    { "rank": 1,  "company": "Stripe",        "count": 14, "prev_count": 11, "direction": "up"   },
    { "rank": 2,  "company": "Salesforce",    "count": 12, "prev_count": 12, "direction": "flat" },
    { "rank": 3,  "company": "Google",        "count": 11, "prev_count": 0,  "direction": "new"  },
    { "rank": 4,  "company": "Microsoft",     "count": 10, "prev_count": 10, "direction": "flat" },
    { "rank": 5,  "company": "OpenAI",        "count":  9, "prev_count": 7,  "direction": "up"   },
    { "rank": 6,  "company": "Anthropic",     "count":  8, "prev_count": 0,  "direction": "new"  },
    { "rank": 7,  "company": "JPMorgan Chase","count":  7, "prev_count": 7,  "direction": "flat" },
    { "rank": 8,  "company": "Amazon",        "count":  7, "prev_count": 9,  "direction": "down" },
    { "rank": 9,  "company": "Databricks",    "count":  6, "prev_count": 0,  "direction": "new"  },
    { "rank": 10, "company": "Figma",         "count":  5, "prev_count": 5,  "direction": "flat" }
  ]
}
```

**Display format:**
```
Top Companies Hiring PMs with AI Skills
7-day rolling window

 1. Stripe          ██████████████████████  14 jobs  ▲ +3
 2. Salesforce      ████████████████████    12 jobs  ▸
 3. Google          ██████████████████      11 jobs  ★ new
 4. Microsoft       ████████████████        10 jobs  ▸
 5. OpenAI          ███████████████          9 jobs  ▲ +2
 6. Anthropic       █████████████            8 jobs  ★ new
 7. JPMorgan Chase  ████████████             7 jobs  ▸
 8. Amazon          ████████████             7 jobs  ▾ −2
 9. Databricks      ██████████               6 jobs  ★ new
10. Figma           ████████                 5 jobs  ▸
```

**Important caveat in methodology note:** This list reflects companies whose PM postings mention AI skills in the full job description or requirements, captured from public job boards via JSearch. LinkedIn and internal career pages are excluded. The count represents deduplicated distinct job postings, not applicant slots.

#### 6.5 Weekly Digest

A 3-4 sentence AI-generated paragraph published every Saturday, interpreting the week's data against the central thesis. The digest references all four data points: volume trend, AI penetration rate, top skills, and top companies.

Format: digest label (week number) + 3-4 sentence paragraph interpreting the week's data against the central thesis.

Example: *"PM hiring held at 4,200 active postings this week, flat vs. the 7-day average. The AI penetration rate reached 34%, up 5.7 points since tracking began. LLM and agentic skills dominated AI mentions for the third consecutive week. Stripe, Salesforce, and Google led demand for PMs with AI skills -- a pattern consistent with AI-native and AI-investing organizations outpacing traditional employers in PM demand."*

**Post-MVP additions to the digest (not at launch):**
- Narrative status badge ("Evidence favors: Narrative A / B / Inconclusive") — added once there is enough data for a directional read
- Email subscribe CTA embedded in the digest section — added once email infrastructure is live and validated

#### 6.6 Ramp Notice

A persistent notice displayed throughout the ramp-up period, surfacing two honest constraints to the reader: that the observatory is new, and that no pre-AI baseline exists.

**What it communicates:**
- How many days the observatory has been running
- That no pre-AI baseline is available — historical comparison requires accumulated data
- A progress indicator showing days elapsed since Day 1

**Data it needs from the pipeline:**
- `days_since_launch`: integer, increments daily
- No additional API calls required — derived from the snapshot date

**When to show it:** Always visible during the MVP period. Can be retired or moved to the methodology note once the project has meaningful longitudinal depth (a future decision, not a launch gate).

---

## 7. Success Metrics

### The only metric that matters in Week 1

**The daily cron ran cleanly for 7 consecutive days and produced a valid snapshot row each time.**

Everything else is secondary to this. A daily pipeline that runs and writes clean data is the entire product for the first two weeks. If it fails silently or produces garbage, nothing else matters.

### 90-day data quality targets

| Metric | Target | Why |
|---|---|---|
| Clean daily snapshots | 84/84 (12 weeks) | Data reliability is the product |
| Zero silent failures | Alerts fire on every run, success and failure | Pipeline health must be observable |

---

## 8. Methodology Note (Published with Dashboard)

The PM Adaptation Index is a personal research project, not a peer-reviewed study. Known limitations:

**Source coverage is incomplete.** Data is pulled from Adzuna and JSearch. LinkedIn, which holds the largest share of PM postings, is excluded -- no public API exists.

**AI keyword detection is imprecise.** A passing mention and a genuine requirement are both counted. The MVP detects presence, not intent. Nuance improves in later versions.

**AI skill detection is based on job description text, not job title.** A posting qualifies when the full description or requirements mention terms from the AI keyword list -- not when the title includes "AI." This avoids title inflation and anchors the signal to what employers are actually asking for.

**This tracks postings, not hires.** A surge in postings could reflect difficulty filling roles, not growth in demand.

**No pre-AI baseline exists.** All data accumulates from Day 1 of the project. There is no historical data before the pipeline first runs.

**Sector classification is manually curated.** Planned for a future release. Will have gaps and misclassifications, documented publicly.

These limitations define the honest scope of the inquiry. They do not invalidate it.

---

*v1.0: MVP reframe throughout. Vision updated to four questions (volume, AI signal, top skills, top companies). Target users expanded to all PM career stages. §6.4 framing updated from "AI PMs" to "PMs with AI skills" -- qualification is based on job description text, not job title, with data extraction note added (§6.4, §8). Community strategy moved to community_strategy.md. Week-by-week execution plan, post-launch roadmap, and risks removed. Success metrics narrowed to data quality only. 12-month horizon removed.*
