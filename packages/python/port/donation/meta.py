"""Extraction for Meta ("Download your information", JSON) exports.

Scoped to Instagram's export shape specifically — the fixtures this
was built and tested against model Instagram (string_list_data
entries with instagram.com hrefs). Facebook's own export is a
separate product with, plausibly, different URLs and wrapper shapes;
extending to it is out of scope here and would need its own fixtures
and verification rather than being assumed to work from this code.

Meta exports give diet *supply*, not exposure: who/what a donor
follows and liked defines what the feed *could* show, never what it
actually showed. There is no feed-content file in a personal export to
extract exposure from — record_type values here are all supply-side
("follow", "page_like", "like", "search", "ad_topic"), and that's a
property of what Meta hands back, not a gap in this extractor.

Like TikTok's, this schema is unverified against a real export in this
session (see fixtures/meta.py, observed 2026-08-27) — needs checking
against a real de-identified sample before fieldwork.

The encoding fix: Meta's export writer takes correctly-encoded UTF-8
text and, before JSON-serializing it, treats each UTF-8 byte as one
latin-1 codepoint. `s.encode("latin-1").decode("utf-8")` reverses
that, and is applied unconditionally to every text field pulled from
a Meta export rather than only to ones that "look" mangled. That's
safe: latin-1 can encode any single byte 0-255, but for text that was
never mangled, re-decoding those bytes as UTF-8 almost always hits an
invalid byte sequence and raises — caught below, original returned
untouched. Verified directly: correctly-encoded Danish strings
(including ones with æ/ø/å and an en-dash) pass through this function
unchanged; genuinely mangled ones recover the original exactly.
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from typing import Optional

from port.donation.archive_utils import find_by_shape
from port.donation.news_sources import is_news
from port.donation.schema import DonationRecord
from port.donation.timezone import format_copenhagen
from port.safe_data import SafeData


def fix_meta_encoding(s: str) -> str:
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _parse_meta_time(value) -> tuple[Optional[str], Optional[str]]:
    raw = str(value) if value is not None else None
    try:
        dt = datetime.fromtimestamp(int(value), tz=timezone.utc)
        return format_copenhagen(dt), raw
    except (TypeError, ValueError, OSError):
        return None, raw


def _find_top_level_list(zf: zipfile.ZipFile, key: str) -> list:
    match = find_by_shape(zf, lambda path, parsed: isinstance(parsed, dict) and isinstance(parsed.get(key), list))
    return match[1][key] if match is not None else []


def _first_string_list_value(item: SafeData, field: str = "value") -> Optional[str]:
    raw = item.raw()
    if not isinstance(raw, dict) or "string_list_data" not in raw:
        return None
    for s in item.get_list("string_list_data"):
        v = s.get_str(field, default="")
        if v:
            return fix_meta_encoding(v)
    return None


def _extract_connection_records(entries: list, record_type: str) -> list[DonationRecord]:
    """Shared by "following" and "pages_liked" — identical string_list_data(value) wrapper shape."""
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        raw_entry = item.raw() if isinstance(item.raw(), dict) else {}
        cph, raw = _parse_meta_time(raw_entry.get("timestamp"))
        name = _first_string_list_value(item, "value")
        records.append(DonationRecord(
            platform="instagram",
            record_type=record_type,
            timestamp_copenhagen=cph,
            timestamp_utc_raw=raw,
            channel_or_account=name,
            is_news=is_news(name),
            content_ref=None,
            is_ad=False,
            had_parse_error=item.had_errors() or cph is None or name is None,
        ))
    return records


def _extract_post_interaction_records(entries: list, record_type: str) -> list[DonationRecord]:
    """Shared by "liked_posts" and "saved_posts" — {"title": account, "string_list_data": [{"href", "timestamp"}]}."""
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        raw = item.raw() if isinstance(item.raw(), dict) else {}
        title = raw.get("title")
        account = fix_meta_encoding(title) if isinstance(title, str) and title else None
        # item.raw() only leaves scalars unwrapped — a nested dict (each
        # string_list_data element) comes back as its own SafeData, not a
        # plain dict, so this has to go through get_list()/get_int() rather
        # than raw.get(...).get(...), which silently returns nothing here.
        ts = None
        for s in item.get_list("string_list_data"):
            ts = s.get_int("timestamp", default=None)
            break
        cph, raw_ts = _parse_meta_time(ts)
        records.append(DonationRecord(
            platform="instagram",
            record_type=record_type,
            timestamp_copenhagen=cph,
            timestamp_utc_raw=raw_ts,
            channel_or_account=account,
            is_news=is_news(account),
            content_ref=None,
            is_ad=False,
            had_parse_error=cph is None or account is None,
        ))
    return records


def _extract_search_records(entries: list) -> list[DonationRecord]:
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        search_data = item.get_dict("search_data")  # same reasoning as above: a nested dict, not a plain one
        text = search_data.get_str("text", default=None)
        query = fix_meta_encoding(text) if text else None
        cph, raw_ts = _parse_meta_time(search_data.get_int("timestamp", default=None))
        records.append(DonationRecord(
            platform="instagram",
            record_type="search",
            timestamp_copenhagen=cph,
            timestamp_utc_raw=raw_ts,
            channel_or_account=None,
            is_news=None,
            content_ref=query,
            is_ad=False,
            had_parse_error=cph is None or query is None,
        ))
    return records


def _extract_ad_topic_records(entries: list) -> list[DonationRecord]:
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        name = item.get_str("name", default=None)
        topic = fix_meta_encoding(name) if name else None
        records.append(DonationRecord(
            platform="instagram",
            record_type="ad_topic",
            timestamp_copenhagen=None,  # ad topics aren't timestamped in this export
            timestamp_utc_raw=None,
            channel_or_account=None,
            is_news=None,  # a topic label isn't a channel/account
            content_ref=topic,
            is_ad=False,
            had_parse_error=item.had_errors(),
        ))
    return records


def extract_data(zf: zipfile.ZipFile, locale: str = "en") -> list[DonationRecord]:
    """Extract followed accounts, liked pages, liked/saved posts, searches, and ad topics."""
    records: list[DonationRecord] = []
    records.extend(_extract_connection_records(_find_top_level_list(zf, "relationships_following"), "follow"))
    records.extend(_extract_connection_records(_find_top_level_list(zf, "page_likes_v2"), "page_like"))
    records.extend(_extract_post_interaction_records(_find_top_level_list(zf, "likes_media_likes"), "like"))
    records.extend(_extract_post_interaction_records(_find_top_level_list(zf, "saved_saved_media"), "save"))
    records.extend(_extract_search_records(_find_top_level_list(zf, "searches_user_searches")))
    records.extend(_extract_ad_topic_records(_find_top_level_list(zf, "topics_your_topics")))
    return records
