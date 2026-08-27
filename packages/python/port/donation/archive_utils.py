"""Shared helpers for locating and validating files inside export archives.

Two conditions the brief treats as first-class, not edge cases:

- Folder and file names inside archives are localised — a Danish
  export will not contain the literal English path a hardcoded lookup
  would expect. Every extractor locates its target files by content
  shape (what's inside), never by path or filename.

- Exports often default to HTML instead of JSON. `find_by_shape` only
  scans `.json`-extensioned members (a file extension is a technical
  format marker, not a localised word, so filtering on it doesn't
  violate the no-hardcoded-path rule). `has_plausible_html_export`
  separately checks for a non-trivial `.html` file, so an extractor
  that finds nothing in JSON can tell "the data isn't here" apart from
  "the data is here, but as HTML" and raise an actionable error for
  the latter instead of silently returning an empty result.
"""

from __future__ import annotations

import json
import logging
import zipfile
from typing import Callable, Iterator, Optional

logger = logging.getLogger(__name__)

# Skip individual archive members above this size rather than loading
# them fully into memory — exports can run past 100 MB, and no target
# file in this project's extractors is anywhere near this large.
MAX_MEMBER_BYTES = 50_000_000


class ExportFormatError(Exception):
    """The archive looks like it was exported in HTML format instead of JSON."""


def _is_json_path(path: str) -> bool:
    return path.lower().endswith(".json")


def _is_html_path(path: str) -> bool:
    return path.lower().endswith(".html") or path.lower().endswith(".htm")


def iter_json_members(zf: zipfile.ZipFile) -> Iterator[tuple[str, object]]:
    """Yield (path, parsed_json) for every .json member that parses cleanly.

    Members that are too large, undecodable, or not valid JSON are
    skipped (logged at debug level) rather than raising — a single
    corrupt or oversized file elsewhere in the archive shouldn't stop
    extraction of everything else.
    """
    for info in zf.infolist():
        if info.is_dir() or not _is_json_path(info.filename):
            continue
        if info.file_size > MAX_MEMBER_BYTES:
            logger.debug("archive_utils: skipping oversized member %s (%d bytes)", info.filename, info.file_size)
            continue
        with zf.open(info) as f:
            raw = f.read()
        try:
            yield info.filename, json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.debug("archive_utils: skipping unparseable member %s: %s", info.filename, e)
            continue


def find_by_shape(
    zf: zipfile.ZipFile, shape_test: Callable[[str, object], bool]
) -> Optional[tuple[str, object]]:
    """Return the first (path, parsed_json) whose content satisfies shape_test, or None.

    shape_test inspects the parsed content's structure — e.g. "is this
    a list of dicts with a 'titleUrl' or 'time' key" — never the path.
    """
    for path, parsed in iter_json_members(zf):
        if shape_test(path, parsed):
            return path, parsed
    return None


def find_all_by_shape(
    zf: zipfile.ZipFile, shape_test: Callable[[str, object], bool]
) -> list[tuple[str, object]]:
    """Like find_by_shape but returns every match — needed where a category can legitimately live in more than one file."""
    return [(path, parsed) for path, parsed in iter_json_members(zf) if shape_test(path, parsed)]


def has_plausible_html_export(zf: zipfile.ZipFile, min_size: int = 500) -> bool:
    """True if the archive contains a non-trivial .html file.

    A coarse signal deliberately: it doesn't try to confirm the HTML
    file is specifically the history export (that would mean parsing
    HTML we're about to tell the participant to stop using), just that
    HTML shows up somewhere sized like real content rather than a tiny
    style/manifest file — enough to justify the actionable error.
    """
    for info in zf.infolist():
        if not info.is_dir() and _is_html_path(info.filename) and info.file_size >= min_size:
            return True
    return False
