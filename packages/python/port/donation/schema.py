"""Normalized donation record schema, shared across all three platforms.

Every field earns its place by being something the research question —
measuring negative news in personalised media diets — actually needs.
Raw video titles, post captions, and similar free text are deliberately
NOT part of this schema even though the export files contain them: the
news/not-news classification runs on the channel/account name, not on
content text, so keeping the text would mean collecting more than the
study needs (a search query is the one exception — for a search event,
the query text *is* the content, not incidental metadata about it).

PARSER_VERSION is stamped onto every record AND onto the donation
payload envelope (see build_payload below). If a platform ships a
schema change (see README's worked example of a YouTube schema
break), donations parsed by the old and the fixed extraction logic
stay distinguishable in the donated data — a researcher can filter out
or reprocess anything from before the fix rather than silently mixing
correct and wrong output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

# Bump whenever a field is added/removed/reinterpreted, or a platform's
# extraction logic changes in a way that could change past output for
# the same input.
PARSER_VERSION = "1.1.0"
# 1.1.0 (2026-08-27): YouTube extraction learned the v2 channel shape
#   ("channel" object alongside the older "subtitles" list). Donations
#   stamped 1.0.0 that came from a v2 export have an empty channel
#   column and cannot be distinguished from genuine news avoiders on
#   their own — see the worked example in the README.
# 1.0.0: initial.

PAYLOAD_SCHEMA_VERSION = "1.0.0"  # envelope shape unchanged by the above


@dataclass
class DonationRecord:
    platform: str
    """"youtube" | "tiktok" | "instagram" | "facebook" — which export this came from; a combined donation mixes platforms."""

    record_type: str
    """"watch" | "search" | "follow" | "like" | "ad_topic" — exposure and supply signals mean different things analytically and must stay distinguishable."""

    timestamp_copenhagen: Optional[str]
    """Analysis timezone (Europe/Copenhagen), ISO-8601. None if the source timestamp couldn't be parsed at all."""

    timestamp_utc_raw: Optional[str]
    """The original timestamp value as found in the export, kept so the UTC-to-Copenhagen conversion is independently checkable."""

    channel_or_account: Optional[str]
    """Who the record is associated with. Input to news classification; None where the export genuinely carries no name (e.g. TikTok watch events)."""

    is_news: Optional[bool]
    """Allowlist match on channel_or_account. None (not False) when there's nothing to check — collapsing that into False would misrepresent "unknown" as "confirmed not news"."""

    content_ref: Optional[str]
    """Stable pointer to what was engaged with: a video ID/URL, or (for searches) the query text itself. Not the video title or post caption."""

    is_ad: bool
    """True only for YouTube's explicitly-marked ad views — organic and ad-driven exposure are different mechanisms worth keeping apart."""

    had_parse_error: bool
    """True if any field on this record fell back to a default rather than being read cleanly — feeds the canary's field-fill-rate check."""

    parser_version: str = PARSER_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def summarize(records: list[DonationRecord]) -> dict:
    """Aggregate counts for the pre-consent summary — never the full record list at this stage."""
    by_type: dict[str, int] = {}
    for r in records:
        by_type[r.record_type] = by_type.get(r.record_type, 0) + 1
    return {
        "total_records": len(records),
        "news_records": sum(1 for r in records if r.is_news),
        "parse_error_records": sum(1 for r in records if r.had_parse_error),
        "by_record_type": by_type,
    }


def metadata_row(platform: str) -> dict:
    """The one row of the small metadata table shown alongside the records table.

    Feldspar assembles the actual donated JSON client-side from
    whatever PropsUIPromptConsentFormTable objects are on screen at
    donate time (each keyed by its own table id) — there's no single
    Python-side function that builds "the payload" as one object, so
    PAYLOAD_SCHEMA_VERSION is carried into the donation the same way
    upstream's own demo carries static reference data: as its own
    tiny table (see script.py's step_consent), not as a wrapper around
    the records table. PARSER_VERSION is already a column on every
    DonationRecord and doesn't need repeating here, but is included
    for a researcher scanning just this one small table to still see
    it without cross-referencing the records table.
    """
    return {
        "platform": platform,
        "payload_schema_version": PAYLOAD_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
    }
