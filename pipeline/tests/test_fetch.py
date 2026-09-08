"""Tests for fetch.py helper logic and shared fetch status rules (no network)."""

import os
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fetch_status import classify, is_hard_failure, SILENT_ZERO_MESSAGE  # noqa: E402


def test_yesterday_returns_prior_day():
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY", "JSEARCH_API_KEY"):
        os.environ.setdefault(key, "test")
    from fetch import yesterday
    assert yesterday() == date.today() - timedelta(days=1)


def test_status_ok_when_rows_and_no_errors():
    assert classify(50, []) == ("ok", None)


def test_status_partial_when_rows_and_errors():
    assert classify(10, ["Page 3 failed"]) == ("partial", "Page 3 failed")


def test_status_failed_when_zero_rows_and_errors():
    status, msg = classify(0, ["Connection timeout"])
    assert status == "failed"
    assert msg == "Connection timeout"


def test_silent_zero_is_failed_not_ok():
    """HTTP 200 with an empty payload must never be logged as ok."""
    status, msg = classify(0, [])
    assert status == "failed"
    assert msg == SILENT_ZERO_MESSAGE


def test_silent_zero_does_not_abort_step():
    status, msg = classify(0, [])
    assert not is_hard_failure({"status": status, "error_message": msg})


def test_zero_rows_with_errors_aborts_step():
    status, msg = classify(0, ["boom"])
    assert is_hard_failure({"status": status, "error_message": msg})
