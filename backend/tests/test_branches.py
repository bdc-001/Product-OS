from datetime import datetime, timezone

from app.services.codebase import _ist_day, _sort_key
from app.services.time_window import tz


def test_utc_evening_lands_on_next_ist_day():
    # 18:30 UTC = 00:00 IST next day
    assert _ist_day("2026-09-02T18:30:00+00:00") == "2026-09-03"
    assert _ist_day("2026-09-02T18:30:00Z") == "2026-09-03"


def test_ist_afternoon_stays_same_day():
    assert _ist_day("2026-09-02T14:15:00+05:30") == "2026-09-02"


def test_naive_datetime_treated_as_ist():
    naive = datetime(2026, 9, 2, 23, 30)
    stamp = naive.replace(tzinfo=tz()).isoformat()
    assert _ist_day(stamp) == "2026-09-02"


def test_newest_merge_sorts_first():
    older = _sort_key("2026-09-01T18:30:00Z")
    newer = _sort_key("2026-09-02T18:30:00Z")
    assert newer > older
    rows = [{"sort_at": "2026-09-01T18:30:00Z"}, {"sort_at": "2026-09-02T18:30:00Z"}]
    rows.sort(key=lambda item: _sort_key(item["sort_at"]), reverse=True)
    assert rows[0]["sort_at"].startswith("2026-09-02")
