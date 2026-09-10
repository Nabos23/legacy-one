from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

MIN_ALWAYS_INTERVAL_MINUTES = 5

RecurrenceKind = str  # "once" | "daily" | "weekly" | "monthly" | "always" | "custom"


class RecurrenceError(ValueError):
    """Raised for any invalid recurrence config -- callers turn this into a 422."""


def _parse_time_of_day(time_of_day: Optional[str]) -> tuple[int, int]:
    if not time_of_day:
        raise RecurrenceError("time_of_day is required for this recurrence kind.")
    try:
        hh_str, mm_str = time_of_day.split(":")
        hh, mm = int(hh_str), int(mm_str)
    except (ValueError, AttributeError) as exc:
        raise RecurrenceError(f"time_of_day must be HH:MM, got {time_of_day!r}") from exc
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise RecurrenceError(f"time_of_day out of range: {time_of_day!r}")
    return hh, mm


def validate_timezone(tz_name: str) -> None:
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise RecurrenceError(f"Unknown timezone: {tz_name!r}") from exc


def recurrence_to_cron(recurrence: dict) -> Optional[str]:
    """Translate a friendly `recurrence` sub-doc into a canonical cron
    expression. Returns None only for kind="once" (which has no cron -- it
    fires once at `run_at` and then the schedule auto-completes)."""
    kind: RecurrenceKind = recurrence.get("kind", "")

    if kind == "once":
        if not recurrence.get("run_at"):
            raise RecurrenceError("run_at is required for a one-off ('once') schedule.")
        return None

    if kind == "always":
        interval = recurrence.get("interval_minutes")
        if not isinstance(interval, int) or interval < MIN_ALWAYS_INTERVAL_MINUTES:
            raise RecurrenceError(
                f"interval_minutes must be an integer >= {MIN_ALWAYS_INTERVAL_MINUTES}, got {interval!r}"
            )
        return f"*/{interval} * * * *"

    if kind == "daily":
        hh, mm = _parse_time_of_day(recurrence.get("time_of_day"))
        return f"{mm} {hh} * * *"

    if kind == "weekly":
        hh, mm = _parse_time_of_day(recurrence.get("time_of_day"))
        days = recurrence.get("day_of_week") or []
        if not days or not all(isinstance(d, int) and 1 <= d <= 7 for d in days):
            raise RecurrenceError("day_of_week must be a non-empty list of ISO weekdays (1=Mon..7=Sun).")
        # cron uses 0=Sun..6=Sat; ISO uses 1=Mon..7=Sun -- 7 (Sun) maps to cron's 0.
        cron_days = ",".join(str(d % 7) for d in days)
        return f"{mm} {hh} * * {cron_days}"

    if kind == "monthly":
        hh, mm = _parse_time_of_day(recurrence.get("time_of_day"))
        dom = recurrence.get("day_of_month")
        if dom == -1:
            dom_field = "L"
        elif isinstance(dom, int) and 1 <= dom <= 31:
            dom_field = str(dom)
        else:
            raise RecurrenceError("day_of_month must be 1-31, or -1 for 'last day of month'.")
        return f"{mm} {hh} {dom_field} * *"

    if kind == "custom":
        expr = recurrence.get("custom_cron")
        if not expr or not croniter.is_valid(expr):
            raise RecurrenceError(f"custom_cron is not a valid cron expression: {expr!r}")
        return expr

    raise RecurrenceError(f"Unknown recurrence kind: {kind!r}")


def compute_next_run_at(cron_expr: str, tz_name: str, after: datetime) -> datetime:
    """Next UTC fire time strictly after `after`, DST-correct.

    croniter is seeded with a zoneinfo-aware local datetime (not a naive one
    with manual UTC-offset math), so it correctly skips/repeats around DST
    transitions in `tz_name`.
    """
    tz = ZoneInfo(tz_name)
    local_after = after.astimezone(tz)
    it = croniter(cron_expr, local_after)
    next_local: datetime = it.get_next(datetime)
    return next_local.astimezone(timezone.utc)
