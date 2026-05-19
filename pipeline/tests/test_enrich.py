"""Tests for enrichment logic in enrich.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from enrich import (
    normalize_title,
    normalize_company_name,
    compute_dedup_hash,
    match_keywords,
)

SAMPLE_KEYWORDS = [
    "llm",
    "llms",
    "generative ai",
    "gen ai",
    "gpt",
    "agentic",
    "rag",
    "prompt engineering",
    "ai product strategy",
    "responsible ai",
    "machine learning",
    "nlp",
]


# ── AI keyword matching ───────────────────────────────────────────────────────

def test_ai_keyword_match_positive():
    desc = "This role requires deep experience with LLM product strategy and prompt engineering."
    has_ai, matches = match_keywords(desc, SAMPLE_KEYWORDS)
    assert has_ai is True
    assert "llm" in matches


def test_ai_keyword_match_negative():
    desc = "You will own the product roadmap and collaborate with engineering."
    has_ai, matches = match_keywords(desc, SAMPLE_KEYWORDS)
    assert has_ai is False
    assert matches == []


def test_ai_keyword_whole_word_only():
    # "calling" must not match "ai" as substring; "allocation" must not match "llm"
    desc = "You are calling upon all experience in capital allocation across the platform."
    has_ai, matches = match_keywords(desc, ["ai", "llm"])
    assert has_ai is False
    assert matches == []


def test_ai_keyword_phrase_match():
    desc = "We need someone to lead generative ai strategy for our product suite."
    has_ai, matches = match_keywords(desc, SAMPLE_KEYWORDS)
    assert has_ai is True
    assert "generative ai" in matches


def test_ai_keyword_case_insensitive():
    desc = "Experience with RAG pipelines and Prompt Engineering required."
    has_ai, matches = match_keywords(desc, SAMPLE_KEYWORDS)
    assert has_ai is True
    assert "rag" in matches
    assert "prompt engineering" in matches


# ── Title normalization ───────────────────────────────────────────────────────

def test_title_normalization_senior_pm():
    title, seniority = normalize_title("Sr. Product Manager, Growth")
    assert title == "Senior PM"
    assert seniority == "senior"


def test_title_normalization_sr_no_dot():
    title, seniority = normalize_title("Sr Product Manager")
    assert title == "Senior PM"
    assert seniority == "senior"


def test_title_normalization_director():
    title, seniority = normalize_title("Group Product Manager, Platform")
    assert title == "Director"
    assert seniority == "director"


def test_title_normalization_apm():
    title, seniority = normalize_title("Associate Product Manager")
    assert title == "APM"
    assert seniority == "junior"


def test_title_normalization_vp():
    title, seniority = normalize_title("VP of Product")
    assert title == "VP"
    assert seniority == "vp"


def test_title_normalization_cpo():
    title, seniority = normalize_title("Chief Product Officer")
    assert title == "CPO"
    assert seniority == "vp"


def test_title_normalization_staff():
    title, seniority = normalize_title("Principal Product Manager")
    assert title == "Staff PM"
    assert seniority == "staff"


def test_title_normalization_other():
    title, seniority = normalize_title("Head of Partnerships")
    assert title == "Other"
    assert seniority == "unknown"


def test_title_normalization_empty():
    title, seniority = normalize_title("")
    assert title == "Other"
    assert seniority == "unknown"


# ── Company normalization ─────────────────────────────────────────────────────

def test_company_normalize_strips_inc():
    assert normalize_company_name("Acme Corp, Inc.") == "acme corp"


def test_company_normalize_strips_llc():
    assert normalize_company_name("Widget LLC") == "widget"


def test_company_normalize_case_and_whitespace():
    assert normalize_company_name("  BIG CO.  ") == "big co."


def test_company_normalize_empty():
    assert normalize_company_name("") == ""


def test_company_normalize_none():
    assert normalize_company_name(None) == ""


# ── Dedup hash ────────────────────────────────────────────────────────────────

def test_dedup_hash_deterministic():
    h1 = compute_dedup_hash("Acme Inc.", "Senior Product Manager")
    h2 = compute_dedup_hash("Acme Inc.", "Senior Product Manager")
    assert h1 == h2


def test_dedup_hash_different_companies():
    h1 = compute_dedup_hash("Acme Inc.", "Senior Product Manager")
    h2 = compute_dedup_hash("Globex Corp", "Senior Product Manager")
    assert h1 != h2


def test_dedup_hash_different_titles():
    h1 = compute_dedup_hash("Acme Inc.", "Senior Product Manager")
    h2 = compute_dedup_hash("Acme Inc.", "Staff Product Manager")
    assert h1 != h2


def test_dedup_hash_not_week_bucketed():
    # Same company+title, any two calls should produce the same hash
    # (hash no longer contains week bucket)
    h1 = compute_dedup_hash("Stripe", "Product Manager")
    h2 = compute_dedup_hash("Stripe", "Product Manager")
    assert h1 == h2


def test_dedup_hash_normalizes_company_suffix():
    # Inc. vs no suffix should hash identically
    h1 = compute_dedup_hash("Stripe, Inc.", "Product Manager")
    h2 = compute_dedup_hash("Stripe", "Product Manager")
    assert h1 == h2
