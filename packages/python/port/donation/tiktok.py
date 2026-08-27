"""Extraction for TikTok "Download your data" (JSON) exports.

Handles both export generations the brief calls out: an older single
nested JSON file, and a newer one-file-per-category layout. Both are
located by content shape — specifically, by the presence of a
distinctive inner key ("VideoList", "SearchList", "ItemFavoriteList",
"Following") — rather than by path, so it doesn't matter whether that
key lives at the top of its own file or nested three levels down
inside "Activity".

One deliberate exception to "never rely on a hardcoded name": these
are JSON *key names* internal to the export's data structure, not
folder/file paths. The brief's locale requirement is specifically
about paths (observably tool/OS-generated, and known to be
localized); TikTok's internal category keys read as fixed backend
identifiers rather than translated UI text. That's an assumption, not
a verified fact — flagged here since it hasn't been checked against a
real export, same as the rest of this module's schema.

Real limitation baked in deliberately, not a gap in this extractor:
TikTok's browsing-history and like-list entries are {Date, Link}
only — no creator name — so channel_or_account and is_news are always
None for "watch" and "like" records. Following is the only
name-bearing signal, and it's supply-side (who you follow), not
exposure (what you watched).
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from typing import Optional

from port.donation.archive_utils import ExportFormatError, find_by_shape, has_plausible_html_export
from port.donation.news_sources import is_news
from port.donation.schema import DonationRecord
from port.donation.timezone import format_copenhagen
from port.safe_data import SafeData


def _parse_tiktok_time(value) -> tuple[Optional[str], Optional[str]]:
    raw = str(value) if value is not None else None
    if not isinstance(value, str):
        return None, raw
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return format_copenhagen(dt), raw
    except ValueError:
        return None, raw


def _find_category_list(zf: zipfile.ZipFile, key: str) -> list:
    """Find the list stored under `key`, whether as a whole split file or nested under Activity."""
    # New schema: the entire file is {key: [...]}.
    match = find_by_shape(zf, lambda path, parsed: isinstance(parsed, dict) and isinstance(parsed.get(key), list))
    if match is not None:
        return match[1][key]

    # Old schema: {"Activity": {"<some category>": {key: [...]}}} — the
    # category's own name isn't matched on, only that some sub-object
    # under Activity carries this particular inner key.
    def _old_shape(path: str, parsed: object) -> bool:
        if not isinstance(parsed, dict):
            return False
        activity = parsed.get("Activity")
        if not isinstance(activity, dict):
            return False
        return any(isinstance(v, dict) and isinstance(v.get(key), list) for v in activity.values())

    match = find_by_shape(zf, _old_shape)
    if match is not None:
        activity = match[1]["Activity"]
        for v in activity.values():
            if isinstance(v, dict) and isinstance(v.get(key), list):
                return v[key]
    return []


def _extract_link_records(entries: list, record_type: str) -> list[DonationRecord]:
    """Shared by VideoList (watch) and ItemFavoriteList (like) — identical {Date, Link} shape."""
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        raw_entry = item.raw() if isinstance(item.raw(), dict) else {}
        cph, raw = _parse_tiktok_time(raw_entry.get("Date"))
        link = item.get_str("Link", default=None)
        records.append(DonationRecord(
            platform="tiktok",
            record_type=record_type,
            timestamp_copenhagen=cph,
            timestamp_utc_raw=raw,
            channel_or_account=None,  # not present in this export's browsing/like history — see module docstring
            is_news=None,
            content_ref=link,
            is_ad=False,
            had_parse_error=item.had_errors() or cph is None,
        ))
    return records


def _extract_search_records(entries: list) -> list[DonationRecord]:
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        raw_entry = item.raw() if isinstance(item.raw(), dict) else {}
        cph, raw = _parse_tiktok_time(raw_entry.get("Date"))
        term = item.get_str("SearchTerm", default=None)
        records.append(DonationRecord(
            platform="tiktok",
            record_type="search",
            timestamp_copenhagen=cph,
            timestamp_utc_raw=raw,
            channel_or_account=None,
            is_news=None,
            content_ref=term,
            is_ad=False,
            had_parse_error=item.had_errors() or cph is None,
        ))
    return records


def _extract_following_records(entries: list) -> list[DonationRecord]:
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        raw_entry = item.raw() if isinstance(item.raw(), dict) else {}
        cph, raw = _parse_tiktok_time(raw_entry.get("Date"))
        username = item.get_str("UserName", default=None)
        records.append(DonationRecord(
            platform="tiktok",
            record_type="follow",
            timestamp_copenhagen=cph,
            timestamp_utc_raw=raw,
            channel_or_account=username,
            is_news=is_news(username),
            content_ref=None,
            is_ad=False,
            had_parse_error=item.had_errors() or cph is None,
        ))
    return records


def extract_data(zf: zipfile.ZipFile, locale: str = "en") -> list[DonationRecord]:
    """Extract browsing history, search history, likes, and following from a TikTok export.

    Raises ExportFormatError (message-free — script.py supplies the
    locale-appropriate text) if none of the four categories were found
    anywhere in the archive AND it contains a non-trivial .html file —
    a real (unverified) possibility if TikTok's export defaults to
    HTML the same way Google Takeout's does.
    """
    video_list = _find_category_list(zf, "VideoList")
    search_list = _find_category_list(zf, "SearchList")
    like_list = _find_category_list(zf, "ItemFavoriteList")
    following_list = _find_category_list(zf, "Following")

    if not (video_list or search_list or like_list or following_list) and has_plausible_html_export(zf):
        raise ExportFormatError()

    records: list[DonationRecord] = []
    records.extend(_extract_link_records(video_list, "watch"))
    records.extend(_extract_search_records(search_list))
    records.extend(_extract_link_records(like_list, "like"))
    records.extend(_extract_following_records(following_list))
    return records
