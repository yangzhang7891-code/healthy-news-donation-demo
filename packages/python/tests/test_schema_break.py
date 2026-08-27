"""The deliberate schema break — a worked example. See the README.

This file exists to demonstrate, against real code rather than in
prose, that the canary catches the failure mode it was built for: a
platform silently renaming a field so the parser keeps running,
returns the right number of rows, and quietly stops populating the
study's main variable.

Read alongside the git history. The commits are deliberately
sequential:

  step 1  add the changed-schema fixture
  step 2  demonstrate the break and the canary catching it  <- you are here
  step 3  fix the parser, add the regression test
  step 4  write it up in the README

On why the broken state is pinned with xfail(strict=True) rather than
committed as a failing test: a red commit would make the repository's
own CI meaningless for anyone who checks out that revision or bisects
through it. strict=True gives the same evidence without that cost —
the suite stays green while the parser is broken, and it fails loudly
the moment the behaviour changes, which is exactly what step 3 does.
The real failing-canary output is reproduced in the README and in the
step-2 commit message.
"""

from __future__ import annotations

import pytest

from port.donation import youtube
from tests.conftest import counts_by_type, extract, fill_rate

HEALTHY = "youtube/news_heavy_en.zip"
CHANGED = "youtube/schema_v2_news_heavy_en.zip"


class TestTheBreakIsSilent:
    """Everything a count-based check would look at is unchanged."""

    def test_extraction_does_not_raise(self):
        """No exception. This is the whole problem — nothing announces the failure."""
        extract(youtube.extract_data, CHANGED)

    def test_record_count_is_unchanged(self):
        assert len(extract(youtube.extract_data, CHANGED)) == len(extract(youtube.extract_data, HEALTHY))

    def test_counts_by_type_are_unchanged(self):
        assert counts_by_type(extract(youtube.extract_data, CHANGED)) == counts_by_type(
            extract(youtube.extract_data, HEALTHY)
        )

    def test_parse_error_count_is_unchanged(self):
        """The renamed field isn't recorded as an error, because nothing tried to read it."""
        changed = extract(youtube.extract_data, CHANGED)
        healthy = extract(youtube.extract_data, HEALTHY)
        assert sum(1 for r in changed if r.had_parse_error) == sum(1 for r in healthy if r.had_parse_error)

    def test_timestamps_are_still_extracted_normally(self):
        """Confirms the damage is confined to the channel field, not general breakage."""
        changed = extract(youtube.extract_data, CHANGED)
        assert fill_rate(changed, "timestamp_copenhagen") > 0.95


class TestTheDamage:
    """What actually broke — invisible to every check above."""

    def test_channel_names_are_gone(self):
        watch = [r for r in extract(youtube.extract_data, CHANGED) if r.record_type == "watch"]
        assert fill_rate(watch, "channel_or_account") == 0.0

    def test_news_classification_collapses_to_zero(self):
        """The study's main variable. Every donor now looks like a total news avoider."""
        changed = extract(youtube.extract_data, CHANGED)
        healthy = extract(youtube.extract_data, HEALTHY)
        assert sum(1 for r in healthy if r.is_news) == 90
        assert sum(1 for r in changed if r.is_news) == 0


class TestTheCanaryFires:
    """The canary's own thresholds, applied to the broken archive.

    Mirrors the FILL_FLOORS entry for YouTube watch records in
    test_canary.py. If that floor is ever loosened past 0, this stops
    being a meaningful demonstration — which is itself worth knowing.
    """

    CANARY_CHANNEL_FLOOR = 0.85

    def test_healthy_archive_passes_the_floor(self):
        watch = [r for r in extract(youtube.extract_data, HEALTHY) if r.record_type == "watch"]
        assert fill_rate(watch, "channel_or_account") >= self.CANARY_CHANNEL_FLOOR

    def test_changed_archive_breaches_the_floor(self):
        """This is the catch: the assertion the canary would fail on."""
        watch = [r for r in extract(youtube.extract_data, CHANGED) if r.record_type == "watch"]
        assert fill_rate(watch, "channel_or_account") < self.CANARY_CHANNEL_FLOOR


@pytest.mark.xfail(
    strict=True,
    reason="Parser does not yet understand the v2 'channel' field — fixed in Phase 5 step 3.",
)
def test_parser_reads_the_changed_schema():
    """The behaviour we want, pinned as a known failure until step 3 fixes it.

    strict=True means this also fails if it starts passing unexpectedly,
    so the fix cannot land without this marker being removed in the
    same commit.
    """
    watch = [r for r in extract(youtube.extract_data, CHANGED) if r.record_type == "watch"]
    assert fill_rate(watch, "channel_or_account") > 0.85
