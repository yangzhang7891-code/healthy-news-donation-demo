"""Tests for TikTok extraction across both export schema generations.

The headline property here is that the old single-nested-JSON export
and the newer split-file export produce identical output for the same
underlying data. That's what makes "handle both defensively" a
verifiable claim rather than an intention.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from port.donation import tiktok
from port.donation.archive_utils import ExportFormatError
from tests.conftest import archive, counts_by_type, extract, fill_rate

PERSONAS = ["news_heavy", "mixed", "news_avoider"]


def zip_with(members: dict) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, obj in members.items():
            zf.writestr(name, json.dumps(obj, ensure_ascii=False))
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


class TestBothSchemasAgree:
    """The old and new exports carry the same categories in different layouts."""

    @pytest.mark.parametrize("persona", PERSONAS)
    @pytest.mark.parametrize("locale", ["en", "da"])
    def test_old_and_new_schemas_produce_identical_counts(self, persona, locale):
        old = extract(tiktok.extract_data, f"tiktok/old_{persona}_{locale}.zip")
        new = extract(tiktok.extract_data, f"tiktok/new_{persona}_{locale}.zip")
        assert counts_by_type(old) == counts_by_type(new)
        assert len(old) == len(new)

    @pytest.mark.parametrize("persona", PERSONAS)
    def test_old_and_new_schemas_agree_on_news_classification(self, persona):
        old = extract(tiktok.extract_data, f"tiktok/old_{persona}_en.zip")
        new = extract(tiktok.extract_data, f"tiktok/new_{persona}_en.zip")
        assert sum(1 for r in old if r.is_news) == sum(1 for r in new if r.is_news)

    def test_the_two_fixtures_really_do_differ_in_layout(self):
        """Guards the tests above from passing vacuously on accidentally-identical archives."""
        with zipfile.ZipFile(archive("tiktok/old_mixed_en.zip")) as zf:
            old_names = zf.namelist()
        with zipfile.ZipFile(archive("tiktok/new_mixed_en.zip")) as zf:
            new_names = zf.namelist()
        assert len(old_names) == 1  # everything nested in one file
        assert len(new_names) == 4  # one file per category
        assert set(old_names) != set(new_names)


class TestCategoryLocation:
    """Categories are found by their inner key, wherever it sits."""

    VIDEO = {"Date": "2024-03-01 10:15:30", "Link": "https://www.tiktokv.com/share/video/123/"}

    def test_finds_video_list_nested_under_activity(self):
        records = tiktok.extract_data(zip_with({
            "export/user_data.json": {"Activity": {"Video Browsing History": {"VideoList": [self.VIDEO]}}}
        }))
        assert counts_by_type(records) == {"watch": 1}

    def test_finds_video_list_as_its_own_file(self):
        records = tiktok.extract_data(zip_with({"export/Activity/Video Browsing History.json": {"VideoList": [self.VIDEO]}}))
        assert counts_by_type(records) == {"watch": 1}

    def test_finds_category_under_a_danish_path(self):
        records = tiktok.extract_data(zip_with({"eksport/Aktivitet/Videovisningshistorik.json": {"VideoList": [self.VIDEO]}}))
        assert counts_by_type(records) == {"watch": 1}

    def test_danish_fixture_actually_uses_danish_paths(self):
        with zipfile.ZipFile(archive("tiktok/new_mixed_da.zip")) as zf:
            names = zf.namelist()
        assert any("Aktivitet" in n for n in names)
        assert not any("Activity" in n for n in names)


class TestRecordTypes:
    VIDEO_MARCH = {"Date": "2024-03-01 10:15:30", "Link": "https://www.tiktokv.com/share/video/123/"}

    def test_all_four_categories_are_extracted(self):
        records = extract(tiktok.extract_data, "tiktok/new_news_heavy_en.zip")
        assert set(counts_by_type(records)) == {"watch", "search", "like", "follow"}

    def test_following_carries_a_name_and_is_classified(self):
        records = tiktok.extract_data(zip_with({
            "e/Following.json": {"Following": [{"Date": "2024-03-01 10:15:30", "UserName": "drnyheder"}]}
        }))
        assert records[0].record_type == "follow"
        assert records[0].channel_or_account == "drnyheder"
        assert records[0].is_news is True

    def test_search_terms_are_kept_as_content(self):
        records = tiktok.extract_data(zip_with({
            "e/Search History.json": {"SearchList": [{"Date": "2024-03-01 10:15:30", "SearchTerm": "dr nyheder"}]}
        }))
        assert records[0].record_type == "search"
        assert records[0].content_ref == "dr nyheder"

    def test_timestamps_convert_to_copenhagen(self):
        records = tiktok.extract_data(zip_with({"e/v.json": {"VideoList": [self.VIDEO_MARCH]}}))
        assert records[0].timestamp_copenhagen == "2024-03-01T11:15:30+01:00"


class TestNamelessWatchRecords:
    """A real analytical constraint, deliberately preserved.

    TikTok's browsing history is {Date, Link} only — no creator name —
    so news exposure cannot be judged from it. These assertions exist
    so that if a future TikTok export DOES start carrying creator
    names, the change is noticed rather than silently ignored.
    """

    def test_watch_records_have_no_channel(self):
        records = [r for r in extract(tiktok.extract_data, "tiktok/new_mixed_en.zip") if r.record_type == "watch"]
        assert records and all(r.channel_or_account is None for r in records)

    def test_watch_records_are_unknown_not_confirmed_non_news(self):
        records = [r for r in extract(tiktok.extract_data, "tiktok/new_mixed_en.zip") if r.record_type == "watch"]
        assert all(r.is_news is None for r in records)

    def test_only_follow_records_carry_names(self):
        records = extract(tiktok.extract_data, "tiktok/new_news_heavy_en.zip")
        named = {r.record_type for r in records if r.channel_or_account is not None}
        assert named == {"follow"}


class TestMalformedInput:
    def test_malformed_record_is_flagged_not_dropped(self):
        records = tiktok.extract_data(zip_with({
            "e/v.json": {"VideoList": [{"Link": None, "extra_unexpected_field": True}]}
        }))
        assert len(records) == 1
        assert records[0].had_parse_error is True

    def test_unparseable_timestamp_is_flagged_but_raw_value_kept(self):
        records = tiktok.extract_data(zip_with({
            "e/v.json": {"VideoList": [{"Date": "2024-02-30 25:61:00", "Link": "https://x/1/"}]}
        }))
        assert records[0].timestamp_copenhagen is None
        assert records[0].timestamp_utc_raw == "2024-02-30 25:61:00"
        assert records[0].had_parse_error is True

    def test_committed_fixtures_contain_exactly_the_two_injected_bad_records(self):
        records = extract(tiktok.extract_data, "tiktok/new_news_heavy_en.zip")
        assert sum(1 for r in records if r.had_parse_error) == 2


class TestHtmlExport:
    def test_html_only_archive_raises_export_format_error(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("export/history.html", "<html><body>" + "x" * 600 + "</body></html>")
        buffer.seek(0)
        with pytest.raises(ExportFormatError):
            tiktok.extract_data(zipfile.ZipFile(buffer))

    def test_a_valid_json_export_does_not_raise(self):
        extract(tiktok.extract_data, "tiktok/new_mixed_en.zip")


class TestFieldFillRates:
    def test_content_ref_is_populated_for_nearly_every_record(self):
        records = extract(tiktok.extract_data, "tiktok/new_news_heavy_en.zip")
        assert fill_rate(records, "content_ref") > 0.85

    def test_timestamps_are_populated_for_nearly_every_record(self):
        records = extract(tiktok.extract_data, "tiktok/new_news_heavy_en.zip")
        assert fill_rate(records, "timestamp_copenhagen") > 0.95
