"""Scheduling rules for every DAG: run timeout, retries, task limit, sensor timeout.

These numbers exist only here; each DAG passes its schedule to the functions below.
The rules and their reasons are in .agents/rules/airflow-conventions.md
("Scheduling standard"). The module imports nothing from Airflow, so its tests run
in the CI lint environment.
"""

from datetime import datetime, timedelta
from functools import cache

from croniter import croniter

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
SUB_DAILY_RETRY_DELAY = timedelta(minutes=5)
DAILY_RETRIES = 7
DAILY_RETRY_DELAY = timedelta(hours=1)
DAILY_EXECUTION_TIMEOUT = timedelta(hours=6)
SENSOR_TIMEOUT_CAP = 4 * 60 * 60

UNSCHEDULED = (None, "@continuous")

# A fixed anchor keeps the result independent of the parse date; one year covers
# day-of-month and weekday patterns, and the firing cap bounds */5-style crons.
_ANCHOR = datetime(2026, 1, 1)  # noqa: DTZ001 - croniter needs a naive anchor
_HORIZON = timedelta(days=366)
_MAX_FIRINGS = 3000


@cache
def interval_seconds(schedule: str | None) -> int | None:
    """Smallest gap between two consecutive firings; None for an unscheduled DAG."""
    if schedule in UNSCHEDULED:
        return None
    if not isinstance(schedule, str) or not croniter.is_valid(schedule):
        raise ValueError(f"unsupported DAG schedule: {schedule!r}")
    firings = croniter(schedule, _ANCHOR)
    previous = firings.get_next(datetime)
    smallest = None
    for _ in range(_MAX_FIRINGS):
        current = firings.get_next(datetime)
        gap = int((current - previous).total_seconds())
        smallest = gap if smallest is None else min(smallest, gap)
        if current - _ANCHOR > _HORIZON:
            break
        previous = current
    return smallest


def dagrun_timeout(schedule: str | None) -> timedelta:
    """The interval, at least one hour and at most one day; one day if unscheduled.

    Below an hour the interval leaves no room to catch up: after a failure the next
    run of an incremental DAG also loads the failed run's window.
    """
    interval = interval_seconds(schedule)
    if interval is None:
        return DAY
    return min(max(timedelta(seconds=interval), HOUR), DAY)


def task_defaults(schedule: str | None) -> dict:
    """Retry settings and task limit to merge into the DAG's default_args."""
    interval = interval_seconds(schedule)
    if interval is None:
        return {"retries": 0, "retry_exponential_backoff": False}
    if interval < DAY.total_seconds():
        # below an hour the next run soon replaces a failed one and loads its window too
        retries = 0 if interval < HOUR.total_seconds() else 1
        return {
            "retries": retries,
            "retry_delay": SUB_DAILY_RETRY_DELAY,
            "retry_exponential_backoff": False,
        }
    return {
        "retries": DAILY_RETRIES,
        "retry_delay": DAILY_RETRY_DELAY,
        "retry_exponential_backoff": False,
        "execution_timeout": DAILY_EXECUTION_TIMEOUT,
    }


def sensor_timeout(schedule: str | None) -> int:
    """Seconds a cross-DAG sensor may wait: the run timeout, at most four hours."""
    return int(min(dagrun_timeout(schedule).total_seconds(), SENSOR_TIMEOUT_CAP))
