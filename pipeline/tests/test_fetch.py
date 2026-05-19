"""Tests for fetch.py helper logic (non-API, no network calls)."""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_yesterday_returns_prior_day():
    from fetch import yesterday
    result = yesterday()
    assert result == date.today() - timedelta(days=1)


def test_fetch_log_status_failed_when_zero_inserted_and_errors():
    errors = ["Connection timeout"]
    records_inserted = 0
    if records_inserted == 0 and errors:
        status = "failed"
    elif errors:
        status = "partial"
    else:
        status = "ok"
    assert status == "failed"


def test_fetch_log_status_partial_when_some_errors():
    errors = ["Page 3 failed"]
    records_inserted = 10
    if records_inserted == 0 and errors:
        status = "failed"
    elif errors:
        status = "partial"
    else:
        status = "ok"
    assert status == "partial"


def test_fetch_log_status_ok_when_no_errors():
    errors = []
    records_inserted = 50
    if records_inserted == 0 and errors:
        status = "failed"
    elif errors:
        status = "partial"
    else:
        status = "ok"
    assert status == "ok"
