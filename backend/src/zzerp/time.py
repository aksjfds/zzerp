from datetime import UTC, datetime
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


def utc_now() -> datetime:
    return datetime.now(UTC)


def business_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(BUSINESS_TIMEZONE).strftime("%Y-%m-%d %H:%M")
