"""Synthetic Google Takeout YouTube export archives.

Schema assumptions below are based on the shape of real Google Takeout
YouTube exports as commonly documented, observed 2026-08-27. YouTube is
the one platform the project owner can cross-check against a real
(uncommitted, never-shared) Takeout export of their own — if that
export's field names or nesting differ from what's generated here,
this file is what needs correcting, not the extractor.

The Danish folder/file names and title-prefix wording ("Så " for
"Watched ") are a *plausible approximation*, not verified against a
real Danish-locale Takeout — flagging that explicitly per the brief's
own instruction to say so rather than build on an unchecked assumption.

Record shape (JSON, English):
    {
      "header": "YouTube",
      "title": "Watched <video title>",
      "titleUrl": "https://www.youtube.com/watch?v=<11-char id>",
      "subtitles": [{"name": "<channel>", "url": "https://www.youtube.com/channel/<id>"}],
      "time": "2024-03-01T10:15:30.000Z",
      "products": ["YouTube"],
      "activityControls": ["YouTube watch history"]
    }

Ads are marked with a "details": [{"name": "From Google Ads"}] entry.
Removed/private videos keep the "title" field but drop "titleUrl" and
"subtitles" entirely — there is nothing left to identify the video by.
YouTube Music plays are mixed into the same watch-history file with
header "YouTube Music" rather than living in a separate file.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fixtures.archive_builder import ArchiveContent, json_bytes
from fixtures.names_da import (
    NEWS_CHANNELS_DA,
    NEWS_SEARCH_QUERIES_DA,
    NON_NEWS_CHANNELS_DA,
    NON_NEWS_SEARCH_QUERIES_DA,
)
from fixtures.personas import Persona
from fixtures.timestamps import (
    MALFORMED_YOUTUBE_TIME,
    random_utc_timestamp,
    youtube_time_str,
)

VIDEO_TITLE_WORDS_DA = [
    "Nyhedsoverblik", "Interview med", "Analyse af", "Optagelse fra",
    "Reportage om", "Live fra", "Sammendrag af", "Debat om",
]

STRINGS = {
    "en": {
        "watched_prefix": "Watched ",
        "watched_ad": "Watched an ad",
        "watched_removed": "Watched a video that has been removed",
        "search_prefix": "Searched for ",
        "ad_detail": "From Google Ads",
        "takeout_root": "Takeout/YouTube and YouTube Music/history",
        "watch_file": "watch-history.json",
        "search_file": "search-history.json",
        "watch_file_html": "watch-history.html",
        "search_file_html": "search-history.html",
    },
    "da": {
        "watched_prefix": "Så ",
        "watched_ad": "Så en annonce",
        "watched_removed": "Så en video, der er blevet fjernet",
        "search_prefix": "Søgte efter ",
        "ad_detail": "Fra Google Ads",
        "takeout_root": "Takeout/YouTube og YouTube Music/historik",
        "watch_file": "se-historik.json",
        "search_file": "søgehistorik.json",
        "watch_file_html": "se-historik.html",
        "search_file_html": "søgehistorik.html",
    },
}


def _random_id(rng: random.Random, length: int, alphabet: str = string.ascii_letters + string.digits + "_-") -> str:
    return "".join(rng.choice(alphabet) for _ in range(length))


@dataclass
class WatchEvent:
    kind: str  # "video" | "music" | "ad" | "removed"
    time: datetime
    video_id: Optional[str] = None
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    video_title: Optional[str] = None


def _pick_channel(rng: random.Random, persona: Persona) -> tuple[str, bool]:
    is_news = rng.random() < persona.news_share
    pool = NEWS_CHANNELS_DA if is_news else NON_NEWS_CHANNELS_DA
    return rng.choice(pool), is_news


def generate_watch_history(rng: random.Random, persona: Persona) -> list[WatchEvent]:
    """Generate watch events; kind mix is fixed (not persona-dependent) — only news_share varies."""
    events: list[WatchEvent] = []
    for _ in range(persona.activity_count):
        roll = rng.random()
        time = random_utc_timestamp(rng)
        if roll < 0.06:
            events.append(WatchEvent(kind="removed", time=time))
        elif roll < 0.11:
            channel_name, _ = _pick_channel(rng, persona)
            events.append(WatchEvent(
                kind="ad", time=time,
                video_id=_random_id(rng, 11),
                channel_name=channel_name,
                channel_id="UC" + _random_id(rng, 22),
                video_title=f"{rng.choice(VIDEO_TITLE_WORDS_DA)} {channel_name}",
            ))
        else:
            channel_name, is_news = _pick_channel(rng, persona)
            kind = "music" if (roll > 0.85 and not is_news) else "video"
            events.append(WatchEvent(
                kind=kind, time=time,
                video_id=_random_id(rng, 11),
                channel_name=channel_name,
                channel_id="UC" + _random_id(rng, 22),
                video_title=f"{rng.choice(VIDEO_TITLE_WORDS_DA)} {channel_name}",
            ))
    return events


def render_watch_record(event: WatchEvent, locale: str) -> dict:
    s = STRINGS[locale]
    header = "YouTube Music" if event.kind == "music" else "YouTube"
    if event.kind == "removed":
        return {
            "header": "YouTube",
            "title": s["watched_removed"],
            "time": youtube_time_str(event.time),
            "products": ["YouTube"],
            "activityControls": ["YouTube watch history"],
        }
    record = {
        "header": header,
        "title": (s["watched_ad"] if event.kind == "ad" else s["watched_prefix"] + (event.video_title or "")),
        "titleUrl": f"https://www.youtube.com/watch?v={event.video_id}",
        "subtitles": [{
            "name": event.channel_name,
            "url": f"https://www.youtube.com/channel/{event.channel_id}",
        }],
        "time": youtube_time_str(event.time),
        "products": [header],
        "activityControls": ["YouTube watch history"],
    }
    if event.kind == "ad":
        record["details"] = [{"name": s["ad_detail"]}]
    return record


def generate_search_history(rng: random.Random, persona: Persona) -> list[dict]:
    records = []
    count = max(5, persona.activity_count // 4)
    for _ in range(count):
        is_news = rng.random() < persona.news_share
        query = rng.choice(NEWS_SEARCH_QUERIES_DA if is_news else NON_NEWS_SEARCH_QUERIES_DA)
        time = random_utc_timestamp(rng)
        records.append({
            "header": "YouTube",
            "title": STRINGS["en"]["search_prefix"] + query,  # locale applied at render time
            "titleUrl": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
            "time": youtube_time_str(time),
            "_query": query,  # internal only, stripped before serialization
        })
    return records


def render_search_record(record: dict, locale: str) -> dict:
    s = STRINGS[locale]
    return {
        "header": "YouTube",
        "title": s["search_prefix"] + record["_query"],
        "titleUrl": record["titleUrl"],
        "time": record["time"],
    }


def _malformed_watch_record() -> dict:
    """One structurally broken record: wrong types across the board, no titleUrl."""
    return {"header": "YouTube", "title": None, "subtitles": "not-a-list", "time": 20240301}


def _bad_timestamp_watch_record(rng: random.Random) -> dict:
    """An otherwise well-formed record whose time field cannot be parsed."""
    return {
        "header": "YouTube",
        "title": "Watched " + rng.choice(VIDEO_TITLE_WORDS_DA),
        "titleUrl": f"https://www.youtube.com/watch?v={_random_id(rng, 11)}",
        "subtitles": [{"name": rng.choice(NEWS_CHANNELS_DA), "url": "https://www.youtube.com/channel/UCbadtime0000000000000"}],
        "time": MALFORMED_YOUTUBE_TIME,
    }


def build_archive(persona: Persona, locale: str, seed: int, include_edge_cases: bool = True) -> ArchiveContent:
    rng = random.Random(f"{seed}-youtube-{persona.name}-{locale}")
    s = STRINGS[locale]

    watch_events = generate_watch_history(rng, persona)
    watch_records = [render_watch_record(e, locale) for e in watch_events]
    if include_edge_cases:
        watch_records.append(_malformed_watch_record())
        watch_records.append(_bad_timestamp_watch_record(rng))
    rng.shuffle(watch_records)

    search_records_raw = generate_search_history(rng, persona)
    search_records = [render_search_record(r, locale) for r in search_records_raw]

    root = s["takeout_root"]
    return {
        f"{root}/{s['watch_file']}": json_bytes(watch_records),
        f"{root}/{s['search_file']}": json_bytes(search_records),
    }


def build_paused_history_archive(locale: str, missing: bool) -> ArchiveContent:
    """Watch history paused: either an empty JSON array, or the file absent entirely.

    Real Takeout behaviour for a paused history isn't something we've
    verified either way — generating both variants so the extractor has
    to handle whichever turns out to be true, rather than guessing.
    """
    s = STRINGS[locale]
    root = s["takeout_root"]
    if missing:
        return {f"{root}/{s['search_file']}": json_bytes([])}
    return {
        f"{root}/{s['watch_file']}": json_bytes([]),
        f"{root}/{s['search_file']}": json_bytes([]),
    }


def _html_row(title_text: str, video_url: str, channel_name: str, channel_url: str, time_text: str) -> str:
    return f"""<div class="outer-cell mdl-cell mdl-cell--12-col mdl-shadow--2dp">
  <div class="mdl-grid">
    <div class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1">
      {title_text} <a href="{video_url}">video</a><br>
      <a href="{channel_url}">{channel_name}</a><br>
      {time_text}
    </div>
  </div>
</div>
"""


def build_html_export_archive(seed: int) -> ArchiveContent:
    """A watch-history export left in Google's default HTML format (JSON not selected).

    Exists to exercise the extractor's HTML-detection path — real donors
    frequently forget to switch Takeout's output format to JSON.
    """
    rng = random.Random(f"{seed}-youtube-html")
    persona = Persona("html_demo", news_share=0.4, activity_count=15)
    events = generate_watch_history(rng, persona)
    rows = []
    for e in events:
        if e.kind == "removed":
            continue
        rows.append(_html_row(
            "Watched", f"https://www.youtube.com/watch?v={e.video_id}",
            e.channel_name or "", f"https://www.youtube.com/channel/{e.channel_id}",
            youtube_time_str(e.time).replace("T", " ").replace(".000Z", " UTC"),
        ))
    html = "<html><body>\n" + "\n".join(rows) + "\n</body></html>\n"
    root = STRINGS["en"]["takeout_root"]
    return {f"{root}/{STRINGS['en']['watch_file_html']}": html}
