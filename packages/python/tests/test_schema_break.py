"""The deliberate schema break — a worked example. See the README.

This file demonstrates, against real code rather than in prose, the
failure mode the canary exists for: a platform silently renames a
field, the parser keeps running, returns the right number of rows, and
quietly stops populating the study's main variable.

Read alongside the git history, which is deliberately sequential:

  step 1  add the changed-schema fixture
  step 2  demonstrate the break, and the canary catching it
  step 3  fix the parser, add the regression test   <- current state
  step 4  write it up in the README

Since step 3, `port.donation.youtube` understands both the v1
(`subtitles` list) and v2 (`channel` object) shapes, so the committed
v2 fixture no longer breaks anything — TestTheFix pins that.

The break itself is still demonstrated, using a rename the parser has
NOT been taught (`creators`). That is not a contrivance: it is the
honest general case. Teaching the parser one specific rename does not
make it immune to the next one, and the canary — not the parser — is
what stands between an unknown future rename and a silently ruined
dataset.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from port.donation import youtube
from tests.conftest import archive, counts_by_type, extract, fill_rate

HEALTHY = "youtube/news_heavy_en.zip"
CHANGED = "youtube/schema_v2_news_heavy_en.zip"


def with_channel_field_renamed_to(new_name: str) -> zipfile.ZipFile:
    """The healthy archive, with `subtitles` renamed to something unrecognised.

    Stands in for a future platform change nobody has adapted to yet.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(archive(HEALTHY)) as src, zipfile.ZipFile(buffer, "w") as out:
        for info in src.infolist():
            data = json.loads(src.read(info).decode("utf-8"))
            for entry in data:
                if isinstance(entry, dict) and "subtitles" in entry:
                    entry[new_name] = entry.pop("subtitles")
            out.writestr(info.filename, json.dumps(data, ensure_ascii=False))
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


@pytest.fixture(scope="module")
def unknown_rename():
    return youtube.extract_data(with_channel_field_renamed_to("creators"))


class TestTheBreakIsSilent:
    """Everything a count-based check inspects is unchanged by the break."""

    def test_extraction_does_not_raise(self, unknown_rename):
        """No exception. This is the whole problem — nothing announces the failure."""
        assert unknown_rename is not None

    def test_record_count_is_unchanged(self, unknown_rename):
        assert len(unknown_rename) == len(extract(youtube.extract_data, HEALTHY))

    def test_counts_by_type_are_unchanged(self, unknown_rename):
        assert counts_by_type(unknown_rename) == counts_by_type(extract(youtube.extract_data, HEALTHY))

    def test_parse_error_count_is_unchanged(self, unknown_rename):
        """The renamed field isn't recorded as an error, because nothing tried to read it."""
        healthy = extract(youtube.extract_data, HEALTHY)
        assert sum(1 for r in unknown_rename if r.had_parse_error) == sum(1 for r in healthy if r.had_parse_error)

    def test_timestamps_are_still_extracted_normally(self, unknown_rename):
        """Confirms the damage is confined to the channel field, not general breakage."""
        assert fill_rate(unknown_rename, "timestamp_copenhagen") > 0.95


class TestTheDamage:
    """What actually broke — invisible to every check above."""

    def test_channel_names_are_gone(self, unknown_rename):
        watch = [r for r in unknown_rename if r.record_type == "watch"]
        assert fill_rate(watch, "channel_or_account") == 0.0

    def test_news_classification_collapses_to_zero(self, unknown_rename):
        """The study's main variable. Every donor now looks like a total news avoider."""
        healthy = extract(youtube.extract_data, HEALTHY)
        assert sum(1 for r in healthy if r.is_news) == 90
        assert sum(1 for r in unknown_rename if r.is_news) == 0


class TestTheCanaryFires:
    """The canary's own threshold, applied to a broken archive.

    Mirrors the FILL_FLOORS entry for YouTube watch records in
    test_canary.py. If that floor were ever loosened to 0, this would
    stop being a meaningful demonstration — which is itself worth
    knowing, so the floor is asserted here too.
    """

    CANARY_CHANNEL_FLOOR = 0.85

    def test_the_canary_floor_is_still_meaningful(self):
        from tests.test_canary import FILL_FLOORS

        floors = [f for fx, scope, field, f, _ in FILL_FLOORS
                  if fx == HEALTHY and field == "channel_or_account"]
        assert floors and all(f > 0 for f in floors)

    def test_healthy_archive_passes_the_floor(self):
        watch = [r for r in extract(youtube.extract_data, HEALTHY) if r.record_type == "watch"]
        assert fill_rate(watch, "channel_or_account") >= self.CANARY_CHANNEL_FLOOR

    def test_broken_archive_breaches_the_floor(self, unknown_rename):
        """This is the catch: the assertion the canary would fail on."""
        watch = [r for r in unknown_rename if r.record_type == "watch"]
        assert fill_rate(watch, "channel_or_account") < self.CANARY_CHANNEL_FLOOR


class TestTheFix:
    """Step 3: the parser now reads both the v1 and v2 channel shapes.

    Supporting BOTH rather than migrating to the new one is the point.
    Donations already collected were parsed from v1 exports, and donors
    receive whichever format the platform gives them — a parser that
    only understood v2 would break every v1 export still in
    circulation, trading one silent failure for another.
    """

    def test_channel_names_are_read_from_the_v2_schema(self):
        watch = [r for r in extract(youtube.extract_data, CHANGED) if r.record_type == "watch"]
        assert fill_rate(watch, "channel_or_account") > 0.85

    def test_the_v1_schema_still_works(self):
        watch = [r for r in extract(youtube.extract_data, HEALTHY) if r.record_type == "watch"]
        assert fill_rate(watch, "channel_or_account") > 0.85

    def test_both_schemas_produce_identical_output(self):
        """The strongest statement of the fix: same donor, same data, either format."""
        changed = extract(youtube.extract_data, CHANGED)
        healthy = extract(youtube.extract_data, HEALTHY)
        assert [r.channel_or_account for r in changed] == [r.channel_or_account for r in healthy]
        assert [r.is_news for r in changed] == [r.is_news for r in healthy]

    def test_news_classification_is_restored(self):
        assert sum(1 for r in extract(youtube.extract_data, CHANGED) if r.is_news) == 90

    def test_removed_video_stubs_are_still_not_parse_errors(self):
        """Guards against the fix reintroducing the spurious-error bug on stubs."""
        assert sum(1 for r in extract(youtube.extract_data, CHANGED) if r.had_parse_error) == 2

    def test_records_are_stamped_with_the_bumped_parser_version(self):
        """MONITORING.md requires a PARSER_VERSION bump for a platform break.

        It's what lets a researcher later separate donations parsed by
        the broken logic from ones parsed by the fixed logic, instead of
        silently pooling them.
        """
        from port.donation.schema import PARSER_VERSION

        assert PARSER_VERSION == "1.1.0"
        assert all(r.parser_version == "1.1.0" for r in extract(youtube.extract_data, CHANGED))
