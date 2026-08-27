"""Tests for locale-proof file location and HTML-export detection.

The locale requirement is first-class in this project: a Danish export
contains no English folder names, so anything that finds files by path
will silently return nothing for half the donors. These tests pin the
content-shape approach that replaces path matching.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from port.donation.archive_utils import (
    MAX_MEMBER_BYTES,
    find_all_by_shape,
    find_by_shape,
    has_plausible_html_export,
    iter_json_members,
)


def build_zip(contents: dict[str, bytes | str]) -> zipfile.ZipFile:
    """An in-memory zip, so shape tests don't depend on the committed fixtures."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in contents.items():
            zf.writestr(name, data.encode("utf-8") if isinstance(data, str) else data)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def has_key(key: str):
    return lambda path, parsed: isinstance(parsed, dict) and key in parsed


class TestFindByShape:
    def test_finds_file_regardless_of_english_path(self):
        zf = build_zip({"Takeout/YouTube and YouTube Music/history/watch-history.json": '{"marker": 1}'})
        assert find_by_shape(zf, has_key("marker")) is not None

    def test_finds_same_content_under_a_danish_path(self):
        """The whole point: identical content, localized path, same result."""
        zf = build_zip({"Takeout/YouTube og YouTube Music/historik/se-historik.json": '{"marker": 1}'})
        found = find_by_shape(zf, has_key("marker"))
        assert found is not None
        assert found[1] == {"marker": 1}

    def test_finds_content_at_an_entirely_unexpected_path(self):
        """Guards against a path assumption creeping back in as a substring check."""
        zf = build_zip({"some/unexpected/nesting/hi.json": '{"marker": 1}'})
        assert find_by_shape(zf, has_key("marker")) is not None

    def test_returns_none_when_no_member_matches(self):
        zf = build_zip({"a.json": '{"other": 1}'})
        assert find_by_shape(zf, has_key("marker")) is None

    def test_skips_unparseable_json_without_raising(self):
        """One corrupt file must not stop extraction of everything else."""
        zf = build_zip({"broken.json": "{not valid json", "good.json": '{"marker": 1}'})
        found = find_by_shape(zf, has_key("marker"))
        assert found is not None
        assert found[0] == "good.json"

    def test_ignores_non_json_members(self):
        zf = build_zip({"notes.txt": '{"marker": 1}'})
        assert find_by_shape(zf, has_key("marker")) is None

    def test_find_all_by_shape_returns_every_match(self):
        zf = build_zip({"a.json": '{"marker": 1}', "b.json": '{"marker": 2}', "c.json": '{"other": 3}'})
        assert len(find_all_by_shape(zf, has_key("marker"))) == 2


class TestIterJsonMembers:
    def test_skips_members_over_the_size_cap(self, monkeypatch):
        """Exports can exceed 100 MB; an oversized member is skipped, not loaded into memory.

        The cap is patched down to a few bytes rather than committing a
        50 MB fixture — what's under test is the size comparison, and a
        real oversized file would prove the same thing far more slowly.
        """
        zf = build_zip({"big.json": json.dumps({"marker": "x" * 200})})
        assert len(list(iter_json_members(zf))) == 1  # loaded normally under the real cap

        monkeypatch.setattr("port.donation.archive_utils.MAX_MEMBER_BYTES", 10)
        assert list(iter_json_members(zf)) == []  # same member now skipped

    def test_oversized_member_does_not_hide_a_normal_one(self, monkeypatch):
        zf = build_zip({"big.json": json.dumps({"marker": "x" * 200}), "small.json": '{"marker": 1}'})
        monkeypatch.setattr("port.donation.archive_utils.MAX_MEMBER_BYTES", 60)
        found = [name for name, _ in iter_json_members(zf)]
        assert found == ["small.json"]


class TestHtmlExportDetection:
    def test_detects_a_substantial_html_file(self):
        zf = build_zip({"history/watch-history.html": "<html><body>" + "x" * 600 + "</body></html>"})
        assert has_plausible_html_export(zf) is True

    def test_ignores_a_trivially_small_html_file(self):
        """A tiny stylesheet or manifest shouldn't be mistaken for an HTML export."""
        zf = build_zip({"index.html": "<html></html>"})
        assert has_plausible_html_export(zf) is False

    def test_returns_false_for_a_json_only_archive(self):
        zf = build_zip({"history/watch-history.json": '{"marker": 1}'})
        assert has_plausible_html_export(zf) is False
