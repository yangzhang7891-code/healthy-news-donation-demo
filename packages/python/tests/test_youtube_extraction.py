"""Tests for YouTube (Google Takeout) extraction.

One test per condition listed under "Ground truth" in the project
brief, plus the two that were found by testing rather than by reading
the spec (see the watch/search ambiguity and optional-field cases
below) — those are regression tests for real bugs, so they're the ones
most worth keeping.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from port.donation import youtube
from port.donation.archive_utils import ExportFormatError
from tests.conftest import counts_by_type, extract, fill_rate

WATCH_RECORD = {
    "header": "YouTube",
    "title": "Watched Nyhedsoverblik DR Nyheder",
    "titleUrl": "https://www.youtube.com/watch?v=abc12345678",
    "subtitles": [{"name": "DR Nyheder", "url": "https://www.youtube.com/channel/UCxyz"}],
    "time": "2024-03-01T10:15:30.000Z",
}


def zip_with(members: dict) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, obj in members.items():
            zf.writestr(name, json.dumps(obj, ensure_ascii=False))
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


class TestLocaleIndependence:
    """A Danish export contains no English paths — the brief treats this as first-class."""

    def test_english_and_danish_archives_yield_the_same_structure(self):
        en = extract(youtube.extract_data, "youtube/news_heavy_en.zip")
        da = extract(youtube.extract_data, "youtube/news_heavy_da.zip")
        assert len(en) == len(da) == 152
        assert counts_by_type(en) == counts_by_type(da) == {"watch": 122, "search": 30}

    def test_danish_archive_actually_uses_danish_paths(self):
        """Guards the test above from passing vacuously if fixtures lost their localization."""
        from tests.conftest import archive

        with zipfile.ZipFile(archive("youtube/news_heavy_da.zip")) as zf:
            names = zf.namelist()
        assert any("historik" in n for n in names)
        assert not any("history" in n for n in names)


class TestWatchHistory:
    def test_extracts_channel_video_id_and_local_time(self):
        records = youtube.extract_data(zip_with({"h/watch-history.json": [WATCH_RECORD]}))
        assert len(records) == 1
        r = records[0]
        assert r.record_type == "watch"
        assert r.channel_or_account == "DR Nyheder"
        assert r.content_ref == "abc12345678"
        assert r.timestamp_copenhagen == "2024-03-01T11:15:30+01:00"  # UTC+1 in March
        assert r.is_news is True
        assert r.had_parse_error is False

    def test_youtube_music_entries_are_kept_as_watch_records(self):
        """Music plays share the watch-history file; they're still something the donor consumed."""
        music = {**WATCH_RECORD, "header": "YouTube Music", "products": ["YouTube Music"]}
        records = youtube.extract_data(zip_with({"h/watch-history.json": [music]}))
        assert [r.record_type for r in records] == ["watch"]

    def test_ads_are_flagged(self):
        ad = {**WATCH_RECORD, "details": [{"name": "From Google Ads"}]}
        records = youtube.extract_data(zip_with({"h/watch-history.json": [ad]}))
        assert records[0].is_ad is True

    def test_danish_ad_marker_is_also_flagged(self):
        """The marker's wording is localized; matching is by substring, not exact string."""
        ad = {**WATCH_RECORD, "details": [{"name": "Fra Google Ads"}]}
        records = youtube.extract_data(zip_with({"h/watch-history.json": [ad]}))
        assert records[0].is_ad is True

    def test_ordinary_records_are_not_flagged_as_ads(self):
        records = youtube.extract_data(zip_with({"h/watch-history.json": [WATCH_RECORD]}))
        assert records[0].is_ad is False


class TestRemovedOrPrivateVideos:
    """Stubs keep a title but drop titleUrl and subtitles entirely.

    Tested mixed in among ordinary records, which is how they actually
    occur. A file consisting of nothing but stubs is genuinely
    ambiguous — such entries carry no signal distinguishing watch from
    search history — and is not detected; see
    test_a_file_of_only_stubs_is_a_known_blind_spot below.
    """

    STUB = {"header": "YouTube", "title": "Watched a video that has been removed", "time": "2024-03-01T10:15:30.000Z"}

    @pytest.fixture
    def stub_record(self):
        records = youtube.extract_data(zip_with({"h/watch-history.json": [WATCH_RECORD, self.STUB]}))
        assert len(records) == 2
        return records[1]

    def test_stub_is_still_extracted_as_a_watch_record(self, stub_record):
        assert stub_record.record_type == "watch"

    def test_stub_has_no_channel_or_video_id(self, stub_record):
        assert stub_record.channel_or_account is None
        assert stub_record.content_ref is None

    def test_stub_is_unknown_not_confirmed_non_news(self, stub_record):
        assert stub_record.is_news is None

    def test_stub_is_not_counted_as_a_parse_error(self, stub_record):
        """A removed video is a real gap in what YouTube tells us, not a parsing failure.

        Regression test: routing these through SafeData's error-logging
        accessors previously flagged ~90% of clean records as errors,
        which would have made the canary's error-rate signal useless.
        """
        assert stub_record.had_parse_error is False

    def test_a_file_of_only_stubs_is_a_known_blind_spot(self):
        """Documents a real limitation rather than pretending it's handled.

        Stubs carry only header/title/time — no channel, no URL — so
        nothing in the content distinguishes a stub-only watch history
        from a stub-only search history. Detection returns nothing.
        This needs a donor whose entire history is removed or private
        videos, which is why it's accepted rather than worked around;
        if it ever mattered, the fix would be a filename hint as a
        last-resort tiebreak.
        """
        records = youtube.extract_data(zip_with({"h/watch-history.json": [self.STUB, self.STUB]}))
        assert records == []


class TestPausedHistory:
    """A paused history is a valid state, not a failure — it must not raise."""

    def test_empty_watch_history_file_yields_no_records(self):
        records = extract(youtube.extract_data, "youtube/paused_empty_en.zip")
        assert records == []

    def test_missing_watch_history_file_yields_no_records(self):
        records = extract(youtube.extract_data, "youtube/paused_missing_en.zip")
        assert records == []

    def test_paused_history_does_not_raise_export_format_error(self):
        """An empty archive isn't an HTML export; the two must stay distinguishable."""
        extract(youtube.extract_data, "youtube/paused_empty_da.zip")


class TestHtmlExport:
    def test_html_export_raises_export_format_error(self):
        with pytest.raises(ExportFormatError):
            extract(youtube.extract_data, "youtube/html_export.zip")

    def test_error_carries_no_hardcoded_english_prose(self):
        """script.py supplies locale-appropriate text; the extractor shouldn't embed English."""
        with pytest.raises(ExportFormatError) as excinfo:
            extract(youtube.extract_data, "youtube/html_export.zip")
        assert str(excinfo.value) == ""


class TestMalformedInput:
    def test_malformed_record_is_flagged_not_dropped(self):
        """Silently dropping bad rows would hide a schema break; flagging surfaces it."""
        bad = {"header": "YouTube", "title": None, "subtitles": "not-a-list", "time": 20240301}
        records = youtube.extract_data(zip_with({"h/watch-history.json": [WATCH_RECORD, bad]}))
        assert len(records) == 2
        assert records[1].had_parse_error is True

    def test_unparseable_timestamp_is_flagged_but_raw_value_kept(self):
        """The raw value is retained so a researcher can see what the platform actually sent."""
        bad_time = {**WATCH_RECORD, "time": "2024-13-45T99:99:99.000Z"}
        records = youtube.extract_data(zip_with({"h/watch-history.json": [bad_time]}))
        assert records[0].timestamp_copenhagen is None
        assert records[0].timestamp_utc_raw == "2024-13-45T99:99:99.000Z"
        assert records[0].had_parse_error is True

    def test_committed_fixtures_contain_exactly_the_two_injected_bad_records(self):
        records = extract(youtube.extract_data, "youtube/news_heavy_en.zip")
        assert sum(1 for r in records if r.had_parse_error) == 2


class TestWatchSearchDisambiguation:
    """Regression test for a real bug found while building this parser.

    Search entries also carry `time` and `titleUrl`, so an earlier shape
    test matched both files. Which one won depended on zip entry order,
    silently swapping 122 watch records for 30 search records. Only
    `subtitles` actually distinguishes them.
    """

    SEARCH_RECORD = {
        "header": "YouTube",
        "title": "Searched for dr nyheder direkte",
        "titleUrl": "https://www.youtube.com/results?search_query=dr+nyheder",
        "time": "2024-03-01T10:15:30.000Z",
    }

    def test_watch_and_search_are_not_confused(self):
        records = youtube.extract_data(zip_with({
            "h/watch-history.json": [WATCH_RECORD],
            "h/search-history.json": [self.SEARCH_RECORD],
        }))
        assert counts_by_type(records) == {"watch": 1, "search": 1}

    def test_disambiguation_holds_regardless_of_zip_entry_order(self):
        """The original bug was order-dependent, so order is what this varies."""
        reversed_order = youtube.extract_data(zip_with({
            "h/search-history.json": [self.SEARCH_RECORD],
            "h/watch-history.json": [WATCH_RECORD],
        }))
        assert counts_by_type(reversed_order) == {"watch": 1, "search": 1}

    def test_a_removed_stub_first_does_not_break_watch_detection(self):
        """The stub lacks `subtitles`, so sampling only entry[0] would misclassify the file."""
        stub = {"header": "YouTube", "title": "Watched a removed video", "time": "2024-03-01T10:15:30.000Z"}
        records = youtube.extract_data(zip_with({"h/watch-history.json": [stub, WATCH_RECORD]}))
        assert counts_by_type(records) == {"watch": 2}

    def test_search_query_text_is_kept_without_the_localized_prefix(self):
        records = youtube.extract_data(zip_with({"h/search-history.json": [self.SEARCH_RECORD]}))
        assert records[0].content_ref == "for dr nyheder direkte"


class TestFieldFillRates:
    """The signal the canary depends on — see MONITORING.md.

    A renamed field keeps the row count identical while every value
    silently becomes None, so counts alone can't detect it.
    """

    def test_channel_is_populated_for_nearly_all_watch_records(self):
        records = [r for r in extract(youtube.extract_data, "youtube/news_heavy_en.zip") if r.record_type == "watch"]
        assert fill_rate(records, "channel_or_account") > 0.85

    def test_every_watch_record_with_a_channel_also_got_classified(self):
        """is_news must never be None where a name was actually available to check."""
        records = extract(youtube.extract_data, "youtube/news_heavy_en.zip")
        named = [r for r in records if r.channel_or_account is not None]
        assert named and all(r.is_news is not None for r in named)
