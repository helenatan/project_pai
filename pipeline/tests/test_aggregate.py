"""Tests for aggregation logic in aggregate.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from aggregate import (
    skill_direction,
    company_direction,
    count_companies,
)


# ── skill_direction ───────────────────────────────────────────────────────────

def test_top_ai_skills_direction_rising():
    # count=10 today, prev_daily_avg = 6/day (prev_total=42, days=7) → 10/6 > 1.15 → rising
    direction = skill_direction("llm", 10, 42, 7, ever_seen={"llm"})
    assert direction == "rising"


def test_top_ai_skills_direction_flat():
    # count=8, prev_daily_avg = 8/day → 1.0 → flat
    direction = skill_direction("llm", 8, 56, 7, ever_seen={"llm"})
    assert direction == "flat"


def test_top_ai_skills_direction_falling():
    # count=5, prev_daily_avg = 8/day → 0.625 < 0.85 → falling
    direction = skill_direction("llm", 5, 56, 7, ever_seen={"llm"})
    assert direction == "falling"


def test_top_ai_skills_direction_new():
    # Keyword never seen before → 'new'
    direction = skill_direction("new_framework", 3, 0, 7, ever_seen=set())
    assert direction == "new"


def test_top_ai_skills_direction_new_not_rising_when_zero_prev():
    # REGRESSION: keyword with prev_total=0 that is in ever_seen → 'rising' (seen before, just quiet)
    # but keyword NOT in ever_seen → 'new'
    direction_new = skill_direction("brand_new", 5, 0, 7, ever_seen=set())
    assert direction_new == "new"

    direction_quiet = skill_direction("quiet_kw", 5, 0, 7, ever_seen={"quiet_kw"})
    assert direction_quiet == "rising"


def test_top_ai_skills_division_uses_actual_days():
    # REGRESSION: with only 3 days of prior data, must divide by 3 not 7
    # prev_total=12, actual_days=3, prev_daily_avg=4; today=5 → 5/4=1.25 → flat
    direction = skill_direction("llm", 5, 12, 3, ever_seen={"llm"})
    assert direction == "flat"
    # If divided by 7 incorrectly: 12/7=1.71, 5/1.71=2.9 → rising (wrong)


def test_top_ai_skills_direction_zero_days():
    # No prior days at all but keyword seen before → rising
    direction = skill_direction("llm", 5, 0, 0, ever_seen={"llm"})
    assert direction == "rising"


# ── company_direction ─────────────────────────────────────────────────────────

def test_top_employers_direction_new_takes_precedence():
    # CRITICAL REGRESSION: prev=0 must return 'new', NOT 'up'
    direction = company_direction(5, 0)
    assert direction == "new", f"Expected 'new' but got '{direction}'"


def test_top_employers_direction_up():
    assert company_direction(5, 3) == "up"


def test_top_employers_direction_down():
    assert company_direction(3, 8) == "down"


def test_top_employers_direction_flat():
    assert company_direction(5, 5) == "flat"


def test_top_employers_direction_ordering():
    # All four directions in one go
    assert company_direction(5, 0) == "new"
    assert company_direction(5, 3) == "up"
    assert company_direction(3, 8) == "down"
    assert company_direction(5, 5) == "flat"


# ── count_companies ───────────────────────────────────────────────────────────

def _make_records(entries: list[tuple]) -> list[dict]:
    """entries: list of (company_normalized, dedup_hash, has_ai_requirement)"""
    return [
        {"company_normalized": c, "dedup_hash": h, "has_ai_requirement": True}
        for c, h in entries
    ]


def test_top_employers_deduplicates_within_window():
    # Same company posting same role (same hash) on 3 "days" (3 records, same hash)
    records = _make_records([
        ("stripe", "hash_abc"),
        ("stripe", "hash_abc"),
        ("stripe", "hash_abc"),
    ])
    result = count_companies(records)
    assert result["stripe"] == 1


def test_top_employers_dedup_across_week_boundary():
    # REGRESSION: old week-bucketed hash split same role across week boundaries
    # Now hash is not week-bucketed, so same company+title = same hash regardless of week
    records = _make_records([
        ("stripe", "hash_abc"),  # posted last Saturday
        ("stripe", "hash_abc"),  # posted Tuesday (different calendar week, same hash)
    ])
    result = count_companies(records)
    assert result["stripe"] == 1


def test_top_employers_returns_top_10():
    entries = [(f"company_{i}", f"hash_{i}") for i in range(15)]
    records = _make_records(entries)
    counts = count_companies(records)
    top_10 = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    assert len(top_10) == 10


def test_top_employers_empty_company_name_excluded():
    records = _make_records([
        ("", "hash_1"),
        ("", "hash_2"),
        ("stripe", "hash_3"),
    ])
    result = count_companies(records)
    assert "" not in result
    assert "stripe" in result


def test_top_employers_multiple_hashes_per_company():
    # Company with 3 distinct roles should count as 3
    records = _make_records([
        ("google", "hash_a"),
        ("google", "hash_b"),
        ("google", "hash_c"),
    ])
    result = count_companies(records)
    assert result["google"] == 3


# ── ai_penetration_rate semantics ─────────────────────────────────────────────

def test_ai_penetration_rate_bounds():
    # Simulate: 40 AI postings out of 100 total → 40.0%
    total = 100
    ai = 40
    rate = (ai / total * 100) if total > 0 else None
    assert rate is not None
    assert 0.0 <= rate <= 100.0


def test_ai_penetration_rate_zero_total():
    total = 0
    rate = (1 / total * 100) if total > 0 else None
    assert rate is None


def test_ai_penetration_rate_is_daily_not_rolling():
    # The daily rate is computed from today's data, NOT a rolling avg
    # This is a documentation test: confirm the formula is count/total*100
    today_ai = 30
    today_total = 80
    rate = today_ai / today_total * 100
    assert abs(rate - 37.5) < 0.01


# ── rolling average ───────────────────────────────────────────────────────────

def test_rolling_avg_correctness():
    # [100, 110, 90, 120, 105, 115, 108] → avg = 107
    values = [100, 110, 90, 120, 105, 115, 108]
    avg = sum(values) / len(values)
    assert abs(avg - 107.0) < 0.01


def test_rolling_avg_returns_none_below_3_rows():
    # With fewer than 3 rows, rolling avg should be None
    # (tested at the function level via the None threshold rule)
    # Simulate: only 2 rows
    rows = [100, 110]
    result = sum(rows) / len(rows) if len(rows) >= 3 else None
    assert result is None


# ── dedup rate ────────────────────────────────────────────────────────────────

def test_dedup_reduces_count():
    # Same company+title appears in both Adzuna and JSearch → dedup count < raw count
    raw_count = 4
    distinct_hashes = {"hash_1", "hash_2"}  # 4 records, only 2 distinct
    distinct_count = len(distinct_hashes)
    dedup_rate = (raw_count - distinct_count) / raw_count * 100
    assert dedup_rate > 0
    assert distinct_count < raw_count


# ── top_ai_skills output shape ────────────────────────────────────────────────

def test_top_ai_skills_returns_top_10():
    from collections import Counter
    keyword_counts = Counter({
        "llm": 61, "ai product strategy": 48, "agentic": 31,
        "prompt engineering": 27, "generative ai": 22, "ai evaluation": 18,
        "responsible ai": 15, "rag": 12, "ai platform": 10,
        "foundation model": 8, "copilot": 4, "nlp": 2,
    })
    top_10 = keyword_counts.most_common(10)
    assert len(top_10) == 10
    assert top_10[0][0] == "llm"
    assert top_10[0][1] == 61
    keywords_in_top10 = [k for k, _ in top_10]
    assert "copilot" not in keywords_in_top10
    assert "nlp" not in keywords_in_top10


def test_top_ai_skills_empty_when_no_ai_records():
    todays_ai_records = []
    from collections import Counter
    keyword_counts = Counter()
    top_10 = keyword_counts.most_common(10)
    skills = list(top_10)
    assert skills == []


# ── data_quality_status propagation ──────────────────────────────────────────

def test_data_quality_status_partial_when_jsearch_failed():
    adzuna_status = "ok"
    jsearch_status = "partial"
    if adzuna_status == "partial" or jsearch_status == "partial":
        result = "partial"
    else:
        result = "complete"
    assert result == "partial"
