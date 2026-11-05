"""Время храним в БД как naive UTC, а «сегодня» считаем в часовом поясе пользователя."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def local_date(dt_utc: datetime) -> date:
    return dt_utc.replace(tzinfo=timezone.utc).astimezone(tz()).date()


def end_of_local_day_utc(day: date) -> datetime:
    """Последний момент локального дня `day`, переведённый в naive UTC."""
    local_end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz())
    return local_end.astimezone(timezone.utc).replace(tzinfo=None)


def start_of_local_day_utc(day: date) -> datetime:
    local_start = datetime.combine(day, time.min, tzinfo=tz())
    return local_start.astimezone(timezone.utc).replace(tzinfo=None)
