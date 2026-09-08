"""
fetch_status.py -- Shared status classification for every fetcher.

A fetch that returns zero records is a failure, whether or not the API raised.
Before this rule, an HTTP 200 with an empty payload was logged as "ok", which
let JSearch report success for 12 consecutive days of zero rows (Aug 26 - Sep 6,
2026) without any alert.

Statuses written to fetch_log:
  ok       records fetched, no errors
  partial  records fetched, some errors
  failed   no records fetched (with or without errors)

A "silent zero" (failed, no errors) is recorded but must NOT abort the fetch
step: downstream enrich/aggregate still run and the snapshot is written with
data_quality_status=degraded. check_coverage.py fails the pipeline afterwards
so the alert fires and the digest is skipped. A hard failure (exceptions and no
rows) keeps the old behaviour of exiting non-zero immediately.
"""

SILENT_ZERO_MESSAGE = "returned 0 records with no errors (silent zero)"


def classify(records_fetched: int, errors: list[str]) -> tuple[str, str | None]:
    """Return (status, error_message) for a completed fetch."""
    if records_fetched == 0:
        message = "; ".join(errors) if errors else SILENT_ZERO_MESSAGE
        return "failed", message
    if errors:
        return "partial", "; ".join(errors)
    return "ok", None


def is_hard_failure(result: dict) -> bool:
    """True when the fetch should abort the step: failed AND at least one error."""
    return result["status"] == "failed" and result.get("error_message") != SILENT_ZERO_MESSAGE
