"""Tests for UTC -> Europe/Copenhagen conversion.

Source timestamps are UTC across all three platforms; the analysis
needs Copenhagen local time. The DST cases matter for a media-diet
study: getting the offset wrong shifts evening viewing across a day
boundary, which is exactly the kind of error that survives review
because every timestamp still looks plausible.
"""

from __future__ import annotations

from datetime import datetime, timezone

from port.donation.timezone import COPENHAGEN, format_copenhagen, utc_to_copenhagen


class TestOffsets:
    def test_winter_is_cet_plus_one(self):
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        assert utc_to_copenhagen(dt).utcoffset().total_seconds() == 3600
        assert format_copenhagen(dt) == "2024-01-15T13:00:00+01:00"

    def test_summer_is_cest_plus_two(self):
        dt = datetime(2024, 7, 15, 12, 0, tzinfo=timezone.utc)
        assert utc_to_copenhagen(dt).utcoffset().total_seconds() == 7200
        assert format_copenhagen(dt) == "2024-07-15T14:00:00+02:00"

    def test_naive_datetimes_are_assumed_utc(self):
        """Some export formats carry no offset at all; treating them as local would be wrong."""
        naive = datetime(2024, 1, 15, 12, 0)
        aware = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        assert utc_to_copenhagen(naive) == utc_to_copenhagen(aware)


class TestDstBoundaries:
    def test_spring_forward_crosses_correctly(self):
        """2024-03-31 01:00 UTC — Denmark springs forward at 02:00 local."""
        before = datetime(2024, 3, 31, 0, 30, tzinfo=timezone.utc)
        after = datetime(2024, 3, 31, 1, 30, tzinfo=timezone.utc)
        assert utc_to_copenhagen(before).utcoffset().total_seconds() == 3600
        assert utc_to_copenhagen(after).utcoffset().total_seconds() == 7200

    def test_autumn_back_crosses_correctly(self):
        """2024-10-27 01:00 UTC — Denmark falls back at 03:00 local."""
        before = datetime(2024, 10, 27, 0, 30, tzinfo=timezone.utc)
        after = datetime(2024, 10, 27, 1, 30, tzinfo=timezone.utc)
        assert utc_to_copenhagen(before).utcoffset().total_seconds() == 7200
        assert utc_to_copenhagen(after).utcoffset().total_seconds() == 3600

    def test_late_evening_utc_becomes_next_day_locally(self):
        """The practical consequence: a 23:30 UTC view is 'the next day' in Copenhagen.

        Day-of-week and time-of-day are analysis variables here, so this
        boundary is a substantive result, not a formatting detail.
        """
        dt = datetime(2024, 7, 15, 23, 30, tzinfo=timezone.utc)
        local = utc_to_copenhagen(dt)
        assert (local.day, local.hour) == (16, 1)


class TestTzdataAvailable:
    def test_copenhagen_zone_resolves(self):
        """Fails loudly if the IANA tz database is missing.

        Pyodide doesn't bundle tzdata with the interpreter — it's
        installed via micropip in py_worker.js. Locally the OS usually
        provides it, so this gap would otherwise only appear in the
        browser.
        """
        assert COPENHAGEN.key == "Europe/Copenhagen"
