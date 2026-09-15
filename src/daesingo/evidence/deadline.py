"""Static-calendar safety-report deadline evaluation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ._contract import Contract, parse_rfc3339
from .errors import PolicyConfigurationError

_SEOUL = ZoneInfo("Asia/Seoul")


def _in_coverage(day: date, start: date, end: date) -> None:
    if not start <= day <= end:
        raise PolicyConfigurationError(f"deadline date outside calendar coverage: {day.isoformat()}")


def evaluate_deadline(
    *, occurred_at: str, evaluated_at: str, resolution_status: str, policy: Contract
) -> Contract:
    """Return the deadline condition and deterministic measurement/provenance."""
    occurred = parse_rfc3339(occurred_at).astimezone(_SEOUL)
    evaluated = parse_rfc3339(evaluated_at).astimezone(_SEOUL)
    coverage_start = date.fromisoformat(policy["coverage_start"])
    coverage_end = date.fromisoformat(policy["coverage_end"])
    _in_coverage(occurred.date(), coverage_start, coverage_end)
    _in_coverage(evaluated.date(), coverage_start, coverage_end)

    holiday_dates = {
        date.fromisoformat(item["date"])
        for values in policy["holidays"].values()
        for item in values
    }
    nominal_deadline = occurred.date() + timedelta(days=policy["deadline_rule"]["duration"])
    _in_coverage(nominal_deadline, coverage_start, coverage_end)
    deadline_day = nominal_deadline
    while deadline_day.weekday() >= 5 or deadline_day in holiday_dates:
        deadline_day += timedelta(days=1)
        _in_coverage(deadline_day, coverage_start, coverage_end)
    deadline_exclusive = datetime.combine(deadline_day + timedelta(days=1), time.min, _SEOUL)
    _in_coverage(deadline_day, coverage_start, coverage_end)

    if evaluated >= deadline_exclusive:
        deadline_status = "EXCEEDED"
    elif deadline_day != nominal_deadline:
        deadline_status = "EXTENDED"
    else:
        deadline_status = "OPEN"
    condition = "TIME_RESOLUTION_NEEDS_REVIEW" if resolution_status == "NEEDS_REVIEW" else deadline_status
    return {
        "condition": condition,
        "deadline_status": deadline_status,
        "deadline_date": deadline_day.isoformat(),
        "deadline_exclusive_at": deadline_exclusive.isoformat(),
        "measurement": {
            "actual": int(evaluated.timestamp()),
            "limit": int(deadline_exclusive.timestamp()),
            "unit": "deadline.epoch_seconds",
        },
        "provenance": {
            "policy_ref": policy["policy_ref"],
            "calendar_ref": policy["calendar_ref"],
        },
    }
