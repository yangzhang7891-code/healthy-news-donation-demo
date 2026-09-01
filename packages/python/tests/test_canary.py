"""Canary: does extraction still produce the DATA it used to?

The unit tests answer "does the parser behave correctly on cases we
thought of?" This file answers a different and, for fieldwork, more
urgent question: "has the output drifted from what it was, in a way
nobody predicted?"

That distinction matters because parsers fail silently when platforms
change schemas. The dangerous failure is not an exception — an
exception is loud and gets fixed. The dangerous failure is a parser
that still runs, still returns the right NUMBER of rows, and fills a
column with None. Every donation collected after that point is
quietly missing the study's main variable, and nothing announces it.

So this file asserts on two things no exception-based check would
catch:

  1. Extraction counts, per fixture, against a recorded baseline.
     Catches records disappearing or appearing.
  2. Field-fill rates — the share of records where a field is actually
     populated. Catches a field going empty while the row count stays
     identical, which is exactly what a renamed field looks like.

See MONITORING.md for what to do when this fires.
"""

from __future__ import annotations

import zipfile

import pytest

from port.donation import meta, tiktok, youtube
from tests.conftest import archive, counts_by_type, fill_rate

EXTRACTORS = {"youtube": youtube.extract_data, "tiktok": tiktok.extract_data, "meta": meta.extract_data}

# Recorded from the committed fixtures (seed 42) on 2026-08-27.
#
# These are a SNAPSHOT, not a specification. A diff here means the
# output of extraction changed. That is sometimes correct — you fixed a
# bug, you added a record type — and sometimes a platform schema break.
# The point is that it can never happen unnoticed. Update these numbers
# only with a commit message saying which of the two it was.
BASELINE: dict[str, dict] = {
    "youtube/news_heavy_en.zip": {"total": 152, "by_type": {"watch": 122, "search": 30}, "news": 90, "errors": 2},
    "youtube/news_heavy_da.zip": {"total": 152, "by_type": {"watch": 122, "search": 30}, "news": 78, "errors": 2},
    "youtube/mixed_en.zip": {"total": 127, "by_type": {"watch": 102, "search": 25}, "news": 28, "errors": 2},
    "youtube/mixed_da.zip": {"total": 127, "by_type": {"watch": 102, "search": 25}, "news": 21, "errors": 2},
    "youtube/news_avoider_en.zip": {"total": 114, "by_type": {"watch": 92, "search": 22}, "news": 8, "errors": 2},
    "youtube/news_avoider_da.zip": {"total": 114, "by_type": {"watch": 92, "search": 22}, "news": 1, "errors": 2},
    "tiktok/old_news_heavy_en.zip": {"total": 177, "by_type": {"watch": 122, "search": 24, "like": 20, "follow": 11}, "news": 7, "errors": 2},
    "tiktok/new_news_heavy_en.zip": {"total": 177, "by_type": {"watch": 122, "search": 24, "like": 20, "follow": 11}, "news": 7, "errors": 2},
    "tiktok/old_mixed_en.zip": {"total": 143, "by_type": {"watch": 102, "search": 20, "like": 16, "follow": 5}, "news": 1, "errors": 2},
    "tiktok/new_mixed_en.zip": {"total": 143, "by_type": {"watch": 102, "search": 20, "like": 16, "follow": 5}, "news": 1, "errors": 2},
    "tiktok/old_news_avoider_en.zip": {"total": 129, "by_type": {"watch": 92, "search": 18, "like": 15, "follow": 4}, "news": 0, "errors": 2},
    "tiktok/new_news_avoider_en.zip": {"total": 129, "by_type": {"watch": 92, "search": 18, "like": 15, "follow": 4}, "news": 0, "errors": 2},
    "meta/news_heavy_en.zip": {"total": 132, "by_type": {"follow": 17, "page_like": 12, "like": 40, "save": 40, "search": 20, "ad_topic": 3}, "news": 75, "errors": 2},
    "meta/news_heavy_da.zip": {"total": 132, "by_type": {"follow": 17, "page_like": 12, "like": 40, "save": 40, "search": 20, "ad_topic": 3}, "news": 80, "errors": 2},
    "meta/mixed_en.zip": {"total": 107, "by_type": {"follow": 14, "page_like": 10, "like": 33, "save": 33, "search": 16, "ad_topic": 1}, "news": 27, "errors": 2},
    "meta/news_avoider_en.zip": {"total": 98, "by_type": {"follow": 13, "page_like": 9, "like": 30, "save": 30, "search": 15, "ad_topic": 1}, "news": 1, "errors": 2},
    # The v2-schema archive carries the same donor's activity as
    # youtube/news_heavy_en.zip, so it must produce identical numbers.
    # Any divergence means one of the two supported channel shapes has
    # regressed — see the worked example in the README.
    "youtube/schema_v2_news_heavy_en.zip": {"total": 152, "by_type": {"watch": 122, "search": 30}, "news": 90, "errors": 2},
}

# Minimum share of records that must carry each field, per platform.
#
# Unlike BASELINE these are FLOORS, not snapshots — deliberately set
# below the observed values with headroom, so ordinary fixture churn
# doesn't trip them but a field going empty does. They encode the
# semantic claim "this column is supposed to have data in it", which
# is the claim a schema break violates.
#
# The scope column matters: a floor computed over all records would be
# diluted by record types that legitimately lack the field (TikTok
# watch rows never have a channel), which would make the floor so low
# it could no longer detect anything.
FILL_FLOORS = [
    # (fixture, record types in scope or None for all, field, floor, observed at baseline)
    ("youtube/news_heavy_en.zip", {"watch"}, "channel_or_account", 0.85, 0.96),
    # content_title carries the study's dependent variable (valence has to
    # be read from text, not from a channel name), so it earns a floor of
    # its own — a platform dropping the title would otherwise be invisible.
    ("youtube/news_heavy_en.zip", {"watch"}, "content_title", 0.85, 0.96),
    ("youtube/news_heavy_da.zip", {"watch"}, "content_title", 0.85, 0.96),
    ("youtube/news_heavy_en.zip", {"search"}, "content_title", 0.95, 1.00),
    ("youtube/news_heavy_en.zip", {"watch"}, "content_ref", 0.85, 0.96),
    ("youtube/news_heavy_en.zip", {"search"}, "content_ref", 0.95, 1.00),
    ("youtube/news_heavy_en.zip", None, "timestamp_copenhagen", 0.95, 0.99),
    ("youtube/news_heavy_da.zip", {"watch"}, "channel_or_account", 0.85, 0.96),
    ("youtube/schema_v2_news_heavy_en.zip", {"watch"}, "channel_or_account", 0.85, 0.96),
    ("tiktok/new_news_heavy_en.zip", {"watch", "like"}, "content_ref", 0.95, 1.00),
    ("tiktok/new_news_heavy_en.zip", {"follow"}, "channel_or_account", 0.95, 1.00),
    ("tiktok/new_news_heavy_en.zip", None, "timestamp_copenhagen", 0.95, 0.99),
    ("meta/news_heavy_en.zip", {"follow", "page_like"}, "channel_or_account", 0.85, 0.93),
    ("meta/news_heavy_da.zip", {"follow", "page_like"}, "channel_or_account", 0.85, 0.93),
    ("meta/news_heavy_en.zip", {"search"}, "content_ref", 0.95, 1.00),
]


def run(fixture: str):
    platform = fixture.split("/")[0]
    extractor = EXTRACTORS["meta" if platform == "meta" else platform]
    with zipfile.ZipFile(archive(fixture)) as zf:
        return extractor(zf)


class TestExtractionCounts:
    """Catches records vanishing — the loud half of a schema break."""

    @pytest.mark.parametrize("fixture", sorted(BASELINE))
    def test_counts_match_baseline(self, fixture):
        expected = BASELINE[fixture]
        records = run(fixture)
        assert len(records) == expected["total"], (
            f"{fixture}: extracted {len(records)} records, baseline is {expected['total']}. "
            "See MONITORING.md — decide whether this is an intended change or a schema break."
        )
        assert counts_by_type(records) == expected["by_type"]

    @pytest.mark.parametrize("fixture", sorted(BASELINE))
    def test_news_classification_count_matches_baseline(self, fixture):
        """Drifts if the allowlist changes, or if names stop being extracted/decoded."""
        records = run(fixture)
        assert sum(1 for r in records if r.is_news) == BASELINE[fixture]["news"]

    @pytest.mark.parametrize("fixture", sorted(BASELINE))
    def test_parse_error_count_matches_baseline(self, fixture):
        """Each fixture carries exactly the bad records deliberately injected into it.

        A rise means new input is failing to parse; a fall means the
        deliberately-broken records stopped being detected as broken.
        Both are worth a look.
        """
        records = run(fixture)
        assert sum(1 for r in records if r.had_parse_error) == BASELINE[fixture]["errors"]


class TestFieldFillRates:
    """Catches a field going empty while counts stay identical — the silent half.

    This is the check that would have caught the worked example in the
    README: a renamed channel field left the row count untouched and
    every channel value None.
    """

    @pytest.mark.parametrize("fixture,scope,field,floor,observed", FILL_FLOORS)
    def test_field_is_populated_above_floor(self, fixture, scope, field, floor, observed):
        records = run(fixture)
        if scope is not None:
            records = [r for r in records if r.record_type in scope]
        assert records, f"{fixture}: no records in scope {scope} — the record types themselves changed"
        rate = fill_rate(records, field)
        assert rate >= floor, (
            f"{fixture}: '{field}' populated in only {rate:.1%} of "
            f"{'/'.join(sorted(scope)) if scope else 'all'} records (floor {floor:.0%}, "
            f"was {observed:.0%} at baseline). A field this empty usually means the platform "
            "renamed or moved it — see MONITORING.md."
        )


class TestCrossCuttingInvariants:
    """Properties that should hold no matter how the fixtures change."""

    @pytest.mark.parametrize("fixture", sorted(BASELINE))
    def test_no_fixture_extracts_zero_records(self, fixture):
        """A parser returning nothing at all is the single loudest schema-break signal."""
        assert len(run(fixture)) > 0

    @pytest.mark.parametrize("fixture", sorted(BASELINE))
    def test_every_named_record_is_classified(self, fixture):
        """is_news must never be None where a name was available to check it against."""
        unclassified = [r for r in run(fixture) if r.channel_or_account and r.is_news is None]
        assert not unclassified

    @pytest.mark.parametrize("fixture", sorted(BASELINE))
    def test_parse_errors_stay_a_small_minority(self, fixture):
        """A jump in the error rate means the input shape moved under us."""
        records = run(fixture)
        assert sum(1 for r in records if r.had_parse_error) / len(records) < 0.10

    @pytest.mark.parametrize("fixture", sorted(BASELINE))
    def test_every_record_is_stamped_with_a_parser_version(self, fixture):
        """Donations parsed by different logic have to stay distinguishable later."""
        assert all(r.parser_version for r in run(fixture))

    def test_tiktok_export_generations_still_agree(self):
        """Divergence here means one of the two schema paths has broken."""
        for persona in ["news_heavy", "mixed", "news_avoider"]:
            old = run(f"tiktok/old_{persona}_en.zip")
            new = run(f"tiktok/new_{persona}_en.zip")
            assert counts_by_type(old) == counts_by_type(new), f"{persona}: schema paths disagree"
