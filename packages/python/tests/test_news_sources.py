"""Tests for allowlist matching — the "counts as news" decision.

This is a research decision encoded in port/config/news_allowlist.yaml,
so these tests pin the *matching behaviour*, and deliberately avoid
asserting the full outlet list: adding an outlet is an ordinary
research change that shouldn't break the test suite.
"""

from __future__ import annotations

import pytest

from port.donation.news_sources import is_news, reset_cache


@pytest.fixture(autouse=True)
def _fresh_allowlist():
    """The loaded allowlist is process-cached; reset so tests can't leak state into each other."""
    reset_cache()
    yield
    reset_cache()


class TestMatching:
    @pytest.mark.parametrize("name", ["DR Nyheder", "TV 2 Nyhederne", "Politiken", "Berlingske", "Ekstra Bladet", "Zetland"])
    def test_known_outlets_match_by_display_name(self, name):
        assert is_news(name) is True

    def test_matching_is_case_insensitive(self):
        assert is_news("dr nyheder") is True
        assert is_news("BERLINGSKE") is True

    def test_platform_handles_match_via_aliases(self):
        """Handles are how the same outlet appears on TikTok/Instagram."""
        assert is_news("drnyheder") is True
        assert is_news("ekstrabladet") is True

    def test_substring_match_survives_surrounding_text(self):
        """Meta page names often carry a descriptive tagline around the outlet name."""
        assert is_news("Politiken – dagligt nyhedsoverblik") is True

    def test_non_news_channels_do_not_match(self):
        for name in ["Mormors Køkken", "Gamer Nikolaj", "Fodboldkanalen", "Bagværk med Marie"]:
            assert is_news(name) is False


class TestInformationExactMatch:
    """"Information" is a real outlet AND an ordinary Danish word.

    It's pinned to exact-match in the allowlist precisely so a loose
    substring match can't flag unrelated accounts. These tests are the
    reason that setting exists, so they're worth keeping explicit.
    """

    def test_the_outlet_itself_still_matches(self):
        assert is_news("Information") is True

    def test_its_handle_alias_still_matches(self):
        assert is_news("information_dk") is True

    def test_the_bare_word_inside_another_name_does_not_match(self):
        assert is_news("Mere information om vores kanal") is False
        assert is_news("Teknisk information") is False


class TestUnknownIsNotFalse:
    """Missing data must stay distinguishable from a confirmed negative.

    TikTok watch records genuinely carry no creator name. Returning
    False there would record "confirmed not news" for something never
    checked, quietly biasing any downstream news-share calculation.
    """

    def test_none_name_returns_none(self):
        assert is_news(None) is None

    def test_empty_name_returns_none(self):
        assert is_news("") is None

    def test_a_checked_non_news_name_returns_false_not_none(self):
        assert is_news("Gamer Nikolaj") is False
