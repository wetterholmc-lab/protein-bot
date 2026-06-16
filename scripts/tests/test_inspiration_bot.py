"""Offline tests for the inspiration_bot example's pure logic.

No network or DB — we only exercise the scheduling due-check and schedule validation,
which is exactly the kind of fiddly logic (timezones, cadence, idempotency) worth
pinning down in isolation before composing the bot.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from examples.inspiration_bot.agent import validate_schedule
from examples.inspiration_bot.jobs import is_due
from examples.inspiration_bot.store import User

UTC = ZoneInfo("UTC")
MONDAY_8AM = datetime(2026, 6, 15, 8, 0, tzinfo=UTC)  # 2026-06-15 is a Monday
SATURDAY_8AM = datetime(2026, 6, 20, 8, 0, tzinfo=UTC)


def _user(**kwargs: object) -> User:
    base: dict[str, object] = {
        "telegram_id": 1,
        "send_hour": 8,
        "timezone": "UTC",
        "cadence": "daily",
    }
    base.update(kwargs)
    return User(**base)  # type: ignore[arg-type]


def test_due_on_matching_hour() -> None:
    assert is_due(_user(), MONDAY_8AM) is True


def test_not_due_off_hour() -> None:
    assert is_due(_user(send_hour=9), MONDAY_8AM) is False


def test_paused_is_never_due() -> None:
    assert is_due(_user(paused=True), MONDAY_8AM) is False


def test_weekdays_skips_weekend() -> None:
    assert is_due(_user(cadence="weekdays"), MONDAY_8AM) is True
    assert is_due(_user(cadence="weekdays"), SATURDAY_8AM) is False


def test_weekly_only_mondays() -> None:
    tuesday_8am = datetime(2026, 6, 16, 8, 0, tzinfo=UTC)
    assert is_due(_user(cadence="weekly"), MONDAY_8AM) is True
    assert is_due(_user(cadence="weekly"), tuesday_8am) is False


def test_idempotent_already_sent_today() -> None:
    already = datetime(2026, 6, 15, 7, 0, tzinfo=UTC)
    assert is_due(_user(last_sent_at=already), MONDAY_8AM) is False


def test_due_again_next_day() -> None:
    yesterday = datetime(2026, 6, 14, 8, 0, tzinfo=UTC)
    assert is_due(_user(last_sent_at=yesterday), MONDAY_8AM) is True


def test_validate_schedule_accepts_good_values() -> None:
    assert validate_schedule(7, "Europe/Berlin", "weekdays") == (True, "")
    assert validate_schedule(None, None, None) == (True, "")  # a no-op change is valid


def test_validate_schedule_rejects_bad_values() -> None:
    assert validate_schedule(24, None, None)[0] is False
    assert validate_schedule(None, "Mars/Phobos", None)[0] is False
    assert validate_schedule(None, None, "hourly")[0] is False
