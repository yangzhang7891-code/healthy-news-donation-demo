"""Tests for Meta (Instagram) extraction.

The centrepiece is the encoding bug. Meta's export writer takes
correctly-encoded UTF-8 and writes each byte as a latin-1 codepoint,
so Danish æ/ø/å arrive mangled. A naive parser produces garbage
*without crashing* — no exception, no error count, just quietly wrong
names that then fail to match the news allowlist. That silence is what
makes it worth a dedicated regression test rather than a code comment.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from port.donation import meta
from port.donation.archive_utils import ExportFormatError
from tests.conftest import archive, counts_by_type, extract, fill_rate

# The exact byte-level corruption a real Meta export exhibits.
# "Håndbold Danmark" -> "HÃ¥ndbold Danmark"
MANGLED_HANDBOLD = "Håndbold Danmark".encode("utf-8").decode("latin-1")


def zip_with(members: dict) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, obj in members.items():
            zf.writestr(name, json.dumps(obj, ensure_ascii=False))
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def following(value: str, timestamp: int = 1709287200) -> dict:
    return {"relationships_following": [
        {"timestamp": timestamp, "string_list_data": [{"href": "https://instagram.com/x", "value": value, "timestamp": timestamp}]}
    ]}


class TestEncodingFix:
    def test_mangled_danish_name_is_recovered(self):
        records = meta.extract_data(zip_with({"f/following.json": following(MANGLED_HANDBOLD)}))
        assert records[0].channel_or_account == "Håndbold Danmark"

    def test_the_fixture_really_is_mangled_on_disk(self):
        """Guards the test above from passing vacuously if fixtures stopped reproducing the bug."""
        assert MANGLED_HANDBOLD != "Håndbold Danmark"
        assert "Ã¥" in MANGLED_HANDBOLD

    @pytest.mark.parametrize("original", [
        "Mormors Køkken",       # ø
        "Bagværk med Marie",    # æ
        "Håndbold Danmark",     # å
        "Læser nyheder – dagligt",  # æ plus an en-dash (a 3-byte sequence)
    ])
    def test_every_danish_character_class_round_trips(self, original):
        mangled = original.encode("utf-8").decode("latin-1")
        records = meta.extract_data(zip_with({"f/following.json": following(mangled)}))
        assert records[0].channel_or_account == original

    def test_correctly_encoded_text_is_left_untouched(self):
        """The fix is applied unconditionally, so it must be a no-op on clean text."""
        records = meta.extract_data(zip_with({"f/following.json": following("Håndbold Danmark")}))
        assert records[0].channel_or_account == "Håndbold Danmark"

    def test_plain_ascii_is_unaffected(self):
        records = meta.extract_data(zip_with({"f/following.json": following("DR Nyheder")}))
        assert records[0].channel_or_account == "DR Nyheder"

    def test_mangling_would_break_news_classification_if_unfixed(self):
        """Why this bug matters: it silently corrupts the study's main variable.

        A mangled outlet name no longer matches the allowlist, so the
        donor's news exposure is under-counted with no error anywhere.
        """
        from port.donation.news_sources import is_news

        assert is_news("Zetland".encode("utf-8").decode("latin-1")) is True  # ASCII survives
        mangled_outlet = "Politiken – nyheder".encode("utf-8").decode("latin-1")
        records = meta.extract_data(zip_with({"f/following.json": following(mangled_outlet)}))
        assert records[0].channel_or_account == "Politiken – nyheder"
        assert records[0].is_news is True

    def test_danish_fixture_decodes_end_to_end(self):
        records = extract(meta.extract_data, "meta/news_heavy_da.zip")
        names = {r.channel_or_account for r in records if r.channel_or_account}
        assert "Mormors Køkken" in names
        assert not any("Ã" in n for n in names)

    def test_ad_topics_are_decoded_too(self):
        """Ad topics go through a different code path than names, so they're checked separately."""
        records = extract(meta.extract_data, "meta/news_heavy_da.zip")
        topics = {r.content_ref for r in records if r.record_type == "ad_topic"}
        assert "Håndbold" in topics


class TestSupplySideRecords:
    """Meta gives diet supply, not exposure — the record types reflect that."""

    def test_all_six_categories_are_extracted(self):
        records = extract(meta.extract_data, "meta/news_heavy_en.zip")
        assert set(counts_by_type(records)) == {"follow", "page_like", "like", "save", "search", "ad_topic"}

    def test_no_watch_records_exist(self):
        """A personal export has no feed-content file, so exposure is unobservable here."""
        records = extract(meta.extract_data, "meta/news_heavy_en.zip")
        assert not any(r.record_type == "watch" for r in records)

    def test_followed_news_account_is_classified(self):
        records = meta.extract_data(zip_with({"f/following.json": following("DR Nyheder")}))
        assert records[0].is_news is True

    def test_ad_topics_have_no_timestamp(self):
        """Not a parse failure — this export simply doesn't timestamp them."""
        records = [r for r in extract(meta.extract_data, "meta/news_heavy_en.zip") if r.record_type == "ad_topic"]
        assert records and all(r.timestamp_copenhagen is None for r in records)


class TestLocaleIndependence:
    def test_english_and_danish_archives_yield_the_same_structure(self):
        en = extract(meta.extract_data, "meta/news_heavy_en.zip")
        da = extract(meta.extract_data, "meta/news_heavy_da.zip")
        assert counts_by_type(en) == counts_by_type(da)

    def test_danish_fixture_actually_uses_danish_paths(self):
        with zipfile.ZipFile(archive("meta/news_heavy_da.zip")) as zf:
            names = zf.namelist()
        assert any("forbindelser" in n for n in names)
        assert not any("connections" in n for n in names)


class TestMalformedInput:
    def test_empty_string_list_data_is_flagged(self):
        records = meta.extract_data(zip_with({
            "f/following.json": {"relationships_following": [{"timestamp": 1709287200, "string_list_data": []}]}
        }))
        assert len(records) == 1
        assert records[0].channel_or_account is None
        assert records[0].had_parse_error is True

    def test_unparseable_timestamp_is_flagged_but_raw_value_kept(self):
        records = meta.extract_data(zip_with({"f/following.json": following("DR Nyheder", timestamp="not-a-timestamp")}))
        assert records[0].timestamp_copenhagen is None
        assert records[0].timestamp_utc_raw == "not-a-timestamp"
        assert records[0].had_parse_error is True

    def test_committed_fixtures_contain_exactly_the_two_injected_bad_records(self):
        records = extract(meta.extract_data, "meta/news_heavy_en.zip")
        assert sum(1 for r in records if r.had_parse_error) == 2

    def test_parse_errors_stay_confined_to_follow_records(self):
        """Regression test: nested-SafeData traversal once flagged ~80% of records as errors."""
        records = extract(meta.extract_data, "meta/news_heavy_en.zip")
        assert {r.record_type for r in records if r.had_parse_error} == {"follow"}


class TestHtmlExport:
    def test_html_only_archive_raises_export_format_error(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("export/your_information.html", "<html><body>" + "x" * 600 + "</body></html>")
        buffer.seek(0)
        with pytest.raises(ExportFormatError):
            meta.extract_data(zipfile.ZipFile(buffer))


class TestFieldFillRates:
    def test_names_are_populated_for_most_records(self):
        records = extract(meta.extract_data, "meta/news_heavy_en.zip")
        assert fill_rate(records, "channel_or_account") > 0.70

    def test_every_record_with_a_name_also_got_classified(self):
        records = extract(meta.extract_data, "meta/news_heavy_en.zip")
        named = [r for r in records if r.channel_or_account is not None]
        assert named and all(r.is_news is not None for r in named)
