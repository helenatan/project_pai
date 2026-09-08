"""Tests for the pure coverage evaluation in check_coverage.py (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_coverage import evaluate  # noqa: E402

BASELINE = [30, 30, 27, 30, 29, 30, 30, 27, 30, 30]


def row(fetched, status="ok", error=None):
    return {"records_fetched": fetched, "status": status, "error_message": error}


def test_missing_row_fails():
    assert evaluate(None, BASELINE)[0] == "FAIL"


def test_failed_status_fails_even_with_rows():
    assert evaluate(row(30, status="failed", error="x"), BASELINE)[0] == "FAIL"


def test_normal_volume_passes():
    assert evaluate(row(28), BASELINE)[0] == "PASS"


def test_partial_status_with_normal_volume_passes():
    assert evaluate(row(28, status="partial", error="one board 404"), BASELINE)[0] == "PASS"


def test_below_floor_fails():
    # median 30, floor 10: Aug 25's 10 rows passes, 9 fails
    assert evaluate(row(10), BASELINE)[0] == "PASS"
    assert evaluate(row(9), BASELINE)[0] == "FAIL"


def test_zero_days_do_not_drag_floor_down():
    baseline = BASELINE + [0] * 20
    assert evaluate(row(5), baseline)[0] == "FAIL"


def test_small_baseline_skips_floor_check():
    assert evaluate(row(1), [30, 30, 30])[0] == "PASS"
