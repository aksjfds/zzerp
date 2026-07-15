from datetime import datetime, timezone
from zoneinfo import ZoneInfo


BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def business_now() -> datetime:
    return datetime.now(BUSINESS_TIMEZONE)


def business_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(BUSINESS_TIMEZONE).isoformat(timespec="minutes")
