from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings


PERIOD_HEADLINES = {
    "morning": "Morning briefing",
    "afternoon": "Afternoon update",
    "evening": "Evening wrap",
    "night": "Overnight catch-up",
}

PERIOD_FOCUS = {
    "morning": (
        "Start-of-day. Cover overnight blockers, unanswered tags, and what to start now. "
        "Actions should be start-of-day follow-ups."
    ),
    "afternoon": (
        "Mid-day. Cover work in flight today and decisions needed before end of day. "
        "Skip stale overnight chatter unless it is still open."
    ),
    "evening": (
        "End of day. Highlight what moved today, what is still open tonight, and what carries to tomorrow. "
        "Do not write a morning standup. Actions should close loops tonight or park them for tomorrow."
    ),
    "night": (
        "Overnight catch-up. Cover what happened since the last working session and what is still blocked."
    ),
}


def tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def now_local() -> datetime:
    return datetime.now(tz())


def period_for(moment: datetime | None = None) -> str:
    current = moment or now_local()
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz())
    hour = current.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour <= 23:
        return "evening"
    return "night"


def briefing_label(moment: datetime | None = None) -> str:
    return PERIOD_HEADLINES[period_for(moment)]


def format_ist(dt: datetime | None) -> str:
    if dt is None:
        return ""
    local = dt if dt.tzinfo else dt.replace(tzinfo=tz())
    local = local.astimezone(tz())
    return local.strftime("%a %d %b, %I:%M %p").replace(" 0", " ") + " IST"


def to_utc_naive(dt: datetime) -> datetime:
    """Treat naive datetimes as IST wall-clock, then return UTC naive (Cliq storage)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz())
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def timestamp_in_window(ts: datetime | None, start: datetime, end: datetime) -> bool:
    if ts is None:
        return False
    utc_start, utc_end = to_utc_naive(start), to_utc_naive(end)
    if utc_start <= ts <= utc_end:
        return True
    start_naive = start.replace(tzinfo=None) if start.tzinfo else start
    end_naive = end.replace(tzinfo=None) if end.tzinfo else end
    return start_naive <= ts <= end_naive


@dataclass(frozen=True)
class BriefingWindow:
    start: datetime
    end: datetime
    period: str
    headline: str
    focus: str

    def as_naive(self) -> tuple[datetime, datetime]:
        start = self.start.replace(tzinfo=None) if self.start.tzinfo else self.start
        end = self.end.replace(tzinfo=None) if self.end.tzinfo else self.end
        return start, end


def _at_work_start(day: datetime) -> datetime:
    local = day if day.tzinfo else day.replace(tzinfo=tz())
    return local.replace(hour=settings.standup_hour, minute=0, second=0, microsecond=0)


def _previous_working_day(current: datetime) -> datetime:
    local = current if current.tzinfo else current.replace(tzinfo=tz())
    weekday = local.weekday()
    if weekday == 0:
        days_back = 3
    elif weekday == 6:
        days_back = 2
    else:
        days_back = 1
    return local - timedelta(days=days_back)


def briefing_window(now: datetime | None = None) -> BriefingWindow:
    """Window ends at actual now (IST). Start depends on time of day.

    Morning/night: previous working day's work start → now.
    Afternoon/evening: today's work start → now.
    """
    current = now or now_local()
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz())
    period = period_for(current)
    if period in {"morning", "night"}:
        start = _at_work_start(_previous_working_day(current))
    else:
        start = _at_work_start(current)
        if current < start:
            start = _at_work_start(_previous_working_day(current))
    return BriefingWindow(
        start=start,
        end=current,
        period=period,
        headline=PERIOD_HEADLINES[period],
        focus=PERIOD_FOCUS[period],
    )


def previous_working_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    window = briefing_window(now)
    return window.as_naive()


def jira_jql_date(dt: datetime) -> str:
    local = dt if dt.tzinfo else dt.replace(tzinfo=tz())
    return local.astimezone(tz()).strftime("%Y-%m-%d %H:%M")


def to_millis(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz())
    return int(dt.timestamp() * 1000)


def week_monday(moment: datetime | None = None) -> datetime:
    current = moment or now_local()
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz())
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(days=start.weekday())


def week_range_label(moment: datetime | None = None) -> str:
    monday = week_monday(moment)
    friday = monday + timedelta(days=4)
    if monday.month == friday.month:
        return f"{monday.strftime('%d').lstrip('0')}–{friday.strftime('%d %b %Y')}"
    return f"{monday.strftime('%d %b').lstrip('0')} – {friday.strftime('%d %b %Y')}"
