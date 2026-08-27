"""Loads the news-source allowlist and matches channel/account names against it.

Kept separate from extraction logic per the brief: which outlets count
as "news" is a research decision, auditable in one YAML file
(port/config/news_allowlist.yaml), not string literals scattered
through three extractors.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Optional

import yaml

_ALLOWLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "news_allowlist.yaml"


class _Term(NamedTuple):
    text: str  # already lowercased
    exact: bool


_cache: Optional[list[_Term]] = None


def _load_terms(path: Path = _ALLOWLIST_PATH) -> list[_Term]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    terms: list[_Term] = []
    for outlet in data.get("outlets", []):
        exact = outlet.get("match", "substring") == "exact"
        terms.append(_Term(outlet["name"].lower(), exact))
        for alias in outlet.get("aliases", []):
            terms.append(_Term(alias.lower(), exact))
    return terms


def is_news(name: Optional[str]) -> Optional[bool]:
    """Whether `name` matches an allowlisted outlet.

    Returns None (not False) when there's nothing to check — a record
    with no channel/account name at all is "unknown", not "confirmed
    not news"; collapsing those would misrepresent missing data as a
    negative finding.
    """
    if not name:
        return None
    global _cache
    if _cache is None:
        _cache = _load_terms()
    lowered = name.lower()
    return any((term.text == lowered) if term.exact else (term.text in lowered) for term in _cache)


def reset_cache() -> None:
    """Test-only: force the next is_news() call to reload the allowlist file."""
    global _cache
    _cache = None
