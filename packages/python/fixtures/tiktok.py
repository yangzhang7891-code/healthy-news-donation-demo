"""Synthetic TikTok "Download your data" (JSON) export archives.

Schema assumptions here are based on general public documentation of
TikTok's JSON export as of 2026-08-27 — unlike the YouTube fixtures,
nobody on this project has inspected a real TikTok export directly in
this session. Treat these shapes as a reasonable starting point that
needs validating against a real (de-identified) export before
fieldwork, not as verified ground truth.

Two schema generations are modelled, per the brief:

Old (single nested JSON, one file):
    {"Activity": {"Video Browsing History": {"VideoList": [...]},
                  "Search History": {"SearchList": [...]},
                  "Like List": {"ItemFavoriteList": [...]},
                  "Following List": {"Following": [...]}}}

New (split into one file per category under an Activity/ folder):
    Activity/Video Browsing History.json  -> {"VideoList": [...]}
    Activity/Search History.json          -> {"SearchList": [...]}
    Activity/Like List.json               -> {"ItemFavoriteList": [...]}
    Activity/Following.json               -> {"Following": [...]}

Important limitation baked into these fixtures deliberately: TikTok's
browsing-history entries are just {Date, Link} — no creator name. There
is no content-based way to tell whether a watched video was news from
the browsing history alone; only the Following list (an account-level,
supply-side signal, not an exposure signal) carries names. This mirrors
a real analytical constraint, not a fixture-generation shortcut.
"""

from __future__ import annotations

import random

from fixtures.archive_builder import ArchiveContent, json_bytes
from fixtures.names_da import (
    NEWS_HANDLES_DA,
    NEWS_SEARCH_QUERIES_DA,
    NON_NEWS_HANDLES_DA,
    NON_NEWS_SEARCH_QUERIES_DA,
)
from fixtures.personas import Persona
from fixtures.timestamps import (
    MALFORMED_TIKTOK_TIME,
    random_utc_timestamp,
    tiktok_time_str,
)

ROOTS = {
    "en": "TikTok_Data_Export",
    "da": "TikTok_Data_Eksport",
}

# Danish folder/file names below are a plausible approximation, not a
# verified real Danish-locale TikTok export.
OLD_FILE = {"en": "user_data.json", "da": "brugerdata.json"}
NEW_FOLDER = {"en": "Activity", "da": "Aktivitet"}
NEW_FILES = {
    "en": {
        "video": "Video Browsing History.json",
        "search": "Search History.json",
        "likes": "Like List.json",
        "following": "Following.json",
    },
    "da": {
        "video": "Videovisningshistorik.json",
        "search": "Søgehistorik.json",
        "likes": "Synes godt om-liste.json",
        "following": "Følger.json",
    },
}


def _video_link(rng: random.Random) -> str:
    video_id = "".join(rng.choice("0123456789") for _ in range(19))
    return f"https://www.tiktokv.com/share/video/{video_id}/"


def _generate_video_list(rng: random.Random, persona: Persona) -> list[dict]:
    items = [{"Date": tiktok_time_str(random_utc_timestamp(rng)), "Link": _video_link(rng)}
             for _ in range(persona.activity_count)]
    # One malformed record (missing Date, wrong type for Link) and one
    # otherwise-valid record with an unparseable Date.
    items.append({"Link": None, "extra_unexpected_field": True})
    items.append({"Date": MALFORMED_TIKTOK_TIME, "Link": _video_link(rng)})
    rng.shuffle(items)
    return items


def _generate_search_list(rng: random.Random, persona: Persona) -> list[dict]:
    count = max(5, persona.activity_count // 5)
    items = []
    for _ in range(count):
        is_news = rng.random() < persona.news_share
        term = rng.choice(NEWS_SEARCH_QUERIES_DA if is_news else NON_NEWS_SEARCH_QUERIES_DA)
        items.append({"Date": tiktok_time_str(random_utc_timestamp(rng)), "SearchTerm": term})
    return items


def _generate_like_list(rng: random.Random, persona: Persona) -> list[dict]:
    count = max(3, persona.activity_count // 6)
    return [{"Date": tiktok_time_str(random_utc_timestamp(rng)), "Link": _video_link(rng)}
            for _ in range(count)]


def _generate_following_list(rng: random.Random, persona: Persona) -> list[dict]:
    """Following is supply-side: who you follow, not what you watched."""
    handles = list(NEWS_HANDLES_DA.values()) if persona.news_share > 0.5 else []
    handles += rng.sample(list(NON_NEWS_HANDLES_DA.values()), k=min(4, len(NON_NEWS_HANDLES_DA)))
    if persona.news_share <= 0.5:
        n_news = 1 if persona.news_share > 0.1 else 0
        handles += rng.sample(list(NEWS_HANDLES_DA.values()), k=n_news)
    return [{"Date": tiktok_time_str(random_utc_timestamp(rng)), "UserName": h} for h in handles]


def _generate_categories(rng: random.Random, persona: Persona) -> dict:
    return {
        "VideoList": _generate_video_list(rng, persona),
        "SearchList": _generate_search_list(rng, persona),
        "ItemFavoriteList": _generate_like_list(rng, persona),
        "Following": _generate_following_list(rng, persona),
    }


def build_old_schema_archive(persona: Persona, locale: str, seed: int) -> ArchiveContent:
    """Older TikTok export: everything nested in one JSON file."""
    rng = random.Random(f"{seed}-tiktok-old-{persona.name}-{locale}")
    cats = _generate_categories(rng, persona)
    payload = {
        "Activity": {
            "Video Browsing History": {"VideoList": cats["VideoList"]},
            "Search History": {"SearchList": cats["SearchList"]},
            "Like List": {"ItemFavoriteList": cats["ItemFavoriteList"]},
            "Following List": {"Following": cats["Following"]},
        }
    }
    path = f"{ROOTS[locale]}/{OLD_FILE[locale]}"
    return {path: json_bytes(payload)}


def build_new_schema_archive(persona: Persona, locale: str, seed: int) -> ArchiveContent:
    """Newer TikTok export: one file per category under Activity/."""
    rng = random.Random(f"{seed}-tiktok-new-{persona.name}-{locale}")
    cats = _generate_categories(rng, persona)
    root = f"{ROOTS[locale]}/{NEW_FOLDER[locale]}"
    files = NEW_FILES[locale]
    return {
        f"{root}/{files['video']}": json_bytes({"VideoList": cats["VideoList"]}),
        f"{root}/{files['search']}": json_bytes({"SearchList": cats["SearchList"]}),
        f"{root}/{files['likes']}": json_bytes({"ItemFavoriteList": cats["ItemFavoriteList"]}),
        f"{root}/{files['following']}": json_bytes({"Following": cats["Following"]}),
    }
