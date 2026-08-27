"""Extraction for Google Takeout YouTube exports.

Locates watch-history and search-history by content shape (a list of
dicts carrying a "time" key, plus "titleUrl" for watch entries) — never
by the "Takeout/YouTube and YouTube Music/history/..." path, which is
localised and won't appear verbatim in a Danish export.

Record mapping, per the ground truth this project works from:
- A "removed/private video" stub keeps "title" but drops "titleUrl"
  and "subtitles" — channel_or_account and content_ref both come back
  None, is_news is None (nothing to check), had_parse_error is False
  (this isn't a parse failure, it's a real gap in what YouTube tells us).
- Ads are marked by a "details" list containing an entry whose "name"
  mentions ads — checked by substring, not exact string, since the
  fixture generator's Danish wording ("Fra Google Ads") differs from
  the English ("From Google Ads") and a real Danish export's exact
  phrasing hasn't been verified.
- YouTube Music plays share the same file; header "YouTube Music"
  marks them (still record_type "watch" — it's still something the
  donor watched/listened to).
"""

from __future__ import annotations

import zipfile
from datetime import datetime

from port.donation.archive_utils import (
    ExportFormatError,
    find_by_shape,
    has_plausible_html_export,
)
from port.donation.news_sources import is_news
from port.donation.schema import DonationRecord
from port.donation.timezone import format_copenhagen
from port.safe_data import SafeData


def _looks_like_watch_entry(entry: object) -> bool:
    """A watch entry either carries `subtitles` or points at a video URL.

    Both signals are checked rather than just `subtitles`, because
    `subtitles` is a field name and field names are exactly what a
    platform schema change renames. The URL shape (`watch?v=`) is
    structural and, unlike folder names, not localized — so detection
    survives a rename of the channel field, and the resulting damage
    shows up as an empty channel column that the canary's fill-rate
    check catches, rather than as an undetectable file.
    """
    if not isinstance(entry, dict):
        return False
    if "subtitles" in entry or "channel" in entry:  # v1 and v2 channel fields
        return True
    url = entry.get("titleUrl")
    return isinstance(url, str) and "watch?v=" in url


def _looks_like_search_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    url = entry.get("titleUrl")
    return isinstance(url, str) and "search_query" in url


def _is_watch_history_shape(path: str, parsed: object) -> bool:
    if not isinstance(parsed, list):
        return False
    if len(parsed) == 0:
        return True  # an empty watch-history.json is a real, valid shape (paused history)
    # Scans every entry, not just entry[0]: a removed-video stub carries
    # none of these signals and can legitimately sort first.
    return any(_looks_like_watch_entry(e) for e in parsed)


def _is_search_history_shape(path: str, parsed: object) -> bool:
    """Search entries also carry `time` and `titleUrl`, so the search-specific
    URL is required AND any watch signal disqualifies the file — otherwise
    whichever file the zip happened to list first would win both lookups."""
    if not isinstance(parsed, list):
        return False
    if len(parsed) == 0:
        return True
    return any(_looks_like_search_entry(e) for e in parsed) and not any(_looks_like_watch_entry(e) for e in parsed)


def _parse_youtube_time(value) -> tuple[str | None, str | None]:
    """Returns (copenhagen_iso, raw_str). Both fields of the pair may be independently useful even on failure."""
    raw = str(value) if value is not None else None
    if not isinstance(value, str):
        return None, raw
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return format_copenhagen(dt), raw
    except (ValueError, OverflowError):
        return None, raw


def _first_channel_name(item: SafeData) -> str | None:
    """The channel name, read from whichever schema this export uses.

    Two shapes are accepted, because donations already collected were
    parsed from the older one and still have to keep working:

        v1  "subtitles": [{"name": ..., "url": ...}]   (a list)
        v2  "channel":   {"name": ..., "url": ...}     (a single object)

    Returns None where the export genuinely carries no channel — a
    removed or private video stub has neither key. That's a real gap in
    what YouTube tells us rather than a parse error, so key presence is
    checked before touching SafeData's accessors; routing it through
    get_list() would log a spurious error on every such record and
    drown the error rate the canary watches.
    """
    raw = item.raw()
    if not isinstance(raw, dict):
        return None

    if "subtitles" in raw:
        for sub in item.get_list("subtitles"):
            name = sub.get_str("name", default="")
            if name:
                return name

    if "channel" in raw:
        name = item.get_dict("channel").get_str("name", default="")
        if name:
            return name

    return None


def _is_ad_entry(item: SafeData) -> bool:
    """"details": [{"name": "..."}] mentioning ads — checked by substring, not exact
    string, since the real Danish wording for this marker hasn't been verified.

    Same presence-check reasoning as _first_channel_name: "details" is
    absent on ~90% of normal (non-ad) records — that's not an error.
    """
    raw = item.raw()
    if not isinstance(raw, dict) or "details" not in raw:
        return False
    for d in item.get_list("details"):
        name = d.get_str("name", default="").lower()
        if "ads" in name or "annonce" in name:
            return True
    return False


def _extract_watch_records(entries: list) -> list[DonationRecord]:
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        channel = _first_channel_name(item)
        is_ad = _is_ad_entry(item)
        raw_entry = item.raw() if isinstance(item.raw(), dict) else {}
        cph, raw = _parse_youtube_time(raw_entry.get("time"))
        # Direct dict access, not item.get_str(): a removed/private-video stub
        # has no "titleUrl" at all, which is a real gap YouTube leaves in the
        # export, not a parse error — same reasoning as _first_channel_name.
        video_id = None
        title_url = raw_entry.get("titleUrl")
        if isinstance(title_url, str) and "watch?v=" in title_url:
            video_id = title_url.split("watch?v=")[-1].split("&")[0]

        records.append(DonationRecord(
            platform="youtube",
            record_type="watch",
            timestamp_copenhagen=cph,
            timestamp_utc_raw=raw,
            channel_or_account=channel,
            is_news=is_news(channel),
            content_ref=video_id,
            is_ad=is_ad,
            had_parse_error=item.had_errors() or cph is None,
        ))
    return records


def _extract_search_records(entries: list) -> list[DonationRecord]:
    records = []
    for entry in entries:
        item = SafeData.wrap(entry) if not isinstance(entry, SafeData) else entry
        title = item.get_str("title", default="")
        # "Searched for <query>" (en) / "Søgte efter <query>" (da) — split on the
        # first space-separated prefix rather than hardcoding either language's
        # exact wording, since only the query itself is analytically useful.
        query = title.split(" ", 1)[1] if " " in title else title
        cph, raw = _parse_youtube_time(item.raw().get("time") if isinstance(item.raw(), dict) else None)
        records.append(DonationRecord(
            platform="youtube",
            record_type="search",
            timestamp_copenhagen=cph,
            timestamp_utc_raw=raw,
            channel_or_account=None,
            is_news=None,  # a search query has no channel to check against the allowlist
            content_ref=query or None,
            is_ad=False,
            had_parse_error=item.had_errors() or cph is None,
        ))
    return records


def extract_data(zf: zipfile.ZipFile, locale: str = "en") -> list[DonationRecord]:
    """Extract watch + search history from a Google Takeout YouTube export.

    Raises ExportFormatError (message-free — script.py supplies the
    locale-appropriate text) if the archive looks like it was exported
    in HTML format instead of JSON. Returns an empty list (not an
    error) if watch/search history genuinely isn't present — a paused
    history is a valid state, not a failure.
    """
    watch_match = find_by_shape(zf, _is_watch_history_shape)
    search_match = find_by_shape(zf, _is_search_history_shape)

    if watch_match is None and search_match is None and has_plausible_html_export(zf):
        raise ExportFormatError()

    records: list[DonationRecord] = []
    if watch_match is not None:
        _, watch_entries = watch_match
        records.extend(_extract_watch_records(watch_entries))
    if search_match is not None:
        _, search_entries = search_match
        records.extend(_extract_search_records(search_entries))
    return records
