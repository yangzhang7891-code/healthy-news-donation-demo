"""Deterministic timestamp generation for fixtures.

All three platforms timestamp in UTC (the analysis needs Europe/
Copenhagen local time — that conversion happens in the extraction
code, not here). Also provides the one malformed-timestamp string the
brief requires, so parsers have something realistic to fail on.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

FIXTURE_WINDOW_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
FIXTURE_WINDOW_DAYS = 240


def random_utc_timestamp(rng: random.Random) -> datetime:
    """A deterministic (given rng) UTC timestamp within the fixture window."""
    offset = timedelta(
        days=rng.randint(0, FIXTURE_WINDOW_DAYS),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59),
        seconds=rng.randint(0, 59),
    )
    return FIXTURE_WINDOW_START + offset


def youtube_time_str(dt: datetime) -> str:
    """Google Takeout's watch/search history format: ISO-8601, millis, Z suffix."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def tiktok_time_str(dt: datetime) -> str:
    """TikTok export format: space-separated, no offset. TikTok documents this as UTC."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def meta_epoch_seconds(dt: datetime) -> int:
    """Meta ("Download your information") export format: Unix epoch seconds."""
    return int(dt.timestamp())


# One clearly-broken timestamp per platform, picked to still *look*
# plausible enough that a naive regex-based validity check might miss
# it — the point is to exercise real parsing (datetime.fromisoformat /
# strptime), not a superficial shape check.
MALFORMED_YOUTUBE_TIME = "2024-13-45T99:99:99.000Z"
MALFORMED_TIKTOK_TIME = "2024-02-30 25:61:00"
MALFORMED_META_TIMESTAMP = "not-a-timestamp"
