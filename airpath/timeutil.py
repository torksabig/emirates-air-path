"""UTC timestamps and nearest-hour lookup for archive series."""

from __future__ import annotations

from datetime import datetime, timezone


def parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        if " " in text and "T" not in text:
            text = text.replace(" ", "T", 1)
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    return parse_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def date_utc(value: str | datetime) -> str:
    return parse_utc(value).strftime("%Y-%m-%d")


def nearest_index(times: list[str], target: str | datetime) -> int | None:
    if not times:
        return None
    want = parse_utc(target).timestamp()
    best_i = 0
    best_d = abs(parse_utc(times[0]).timestamp() - want)
    for i, stamp in enumerate(times[1:], start=1):
        d = abs(parse_utc(stamp).timestamp() - want)
        if d < best_d:
            best_d = d
            best_i = i
    return best_i
