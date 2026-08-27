"""Synthetic Meta ("Download your information", JSON) export archives.

Schema assumptions here follow the commonly-documented shape of
Instagram/Facebook's JSON export as of 2026-08-27 — like TikTok, this
has not been checked against a real export in this session. Treat it
as a starting point to validate before fieldwork.

Meta's exports give diet *supply*, not exposure: who/what you follow
and liked defines what the feed could show, not what you actually
saw. That's why these fixtures only cover connections/likes/saves/
searches/inferred-topics — there's no feed-content or watch-time file
to extract from a personal export.

Most list-type files wrap each entry in a `string_list_data` list —
a real, well-documented quirk of these exports, reproduced here:

    {"relationships_following": [
      {"timestamp": 1700000000,
       "string_list_data": [{"href": "...", "value": "<name>", "timestamp": 1700000000}]}
    ]}

The encoding bug: Meta's export writer takes correctly-encoded UTF-8
text and, before JSON-serializing it, treats each UTF-8 byte as one
latin-1 codepoint. `mangle_meta_string` below reproduces that exact
transform so the fixture's on-disk bytes match what a real corrupted
export looks like; the fix on read is
`s.encode("latin-1").decode("utf-8")`.
"""

from __future__ import annotations

import random

from fixtures.archive_builder import ArchiveContent, json_bytes
from fixtures.names_da import (
    NEWS_CHANNELS_DA,
    NEWS_HANDLES_DA,
    NEWS_SEARCH_QUERIES_DA,
    NON_NEWS_CHANNELS_DA,
    NON_NEWS_HANDLES_DA,
    NON_NEWS_SEARCH_QUERIES_DA,
)
from fixtures.personas import Persona
from fixtures.timestamps import MALFORMED_META_TIMESTAMP, meta_epoch_seconds, random_utc_timestamp

ROOTS = {"en": "facebook-export", "da": "facebook-eksport"}

# Danish path segments below are a conservative, unverified guess —
# Meta's category slugs may in fact stay in English regardless of
# account language. Generating the localized variant anyway so the
# extractor is tested against the worse case, per the brief's
# first-class requirement that paths never be hardcoded in English.
PATHS = {
    "en": {
        "following": "connections/followers_and_following/following.json",
        "pages_liked": "pages/likes_and_follows/pages_you_liked.json",
        "liked_posts": "likes_and_reactions/liked_posts.json",
        "saved_posts": "saved/saved_posts.json",
        "search_history": "search_history/your_search_history.json",
        "ad_topics": "ads_information/ad_preferences/ads_interests.json",
    },
    "da": {
        "following": "forbindelser/følgere_og_følger/følger.json",
        "pages_liked": "sider/synes_godt_om_og_følger/sider_du_synes_godt_om.json",
        "liked_posts": "synes_godt_om_og_reaktioner/synes_godt_om_opslag.json",
        "saved_posts": "gemt/gemte_opslag.json",
        "search_history": "søgehistorik/din_søgehistorik.json",
        "ad_topics": "annonceoplysninger/annoncepræferencer/annonceinteresser.json",
    },
}

AD_TOPICS_DA = ["Nyheder", "Musik", "Håndbold", "Madlavning", "Rejser"]

BIO_SUFFIX_DA = " – dagligt nyhedsoverblik på dansk"


def mangle_meta_string(s: str) -> str:
    """Reproduce Meta's export bug: correct UTF-8 text, mis-decoded as latin-1.

    encode('utf-8') gets the real bytes; decode('latin-1') reinterprets
    each of those bytes as one (wrong) codepoint, exactly what Meta's
    writer effectively does before JSON-serializing. Round-trips back
    via `.encode('latin-1').decode('utf-8')`.
    """
    return s.encode("utf-8").decode("latin-1")


def _pick_name(rng: random.Random, persona: Persona) -> tuple[str, bool]:
    is_news = rng.random() < persona.news_share
    pool = NEWS_CHANNELS_DA if is_news else NON_NEWS_CHANNELS_DA
    return rng.choice(pool), is_news


def _string_list_entry(rng: random.Random, name: str, href: str, ts: int) -> dict:
    return {
        "timestamp": ts,
        "string_list_data": [{"href": href, "value": mangle_meta_string(name), "timestamp": ts}],
    }


def _generate_following(rng: random.Random, persona: Persona) -> list[dict]:
    entries = []
    for _ in range(max(6, persona.activity_count // 8)):
        name, is_news = _pick_name(rng, persona)
        handle = NEWS_HANDLES_DA.get(name) or NON_NEWS_HANDLES_DA.get(name, "account")
        ts = meta_epoch_seconds(random_utc_timestamp(rng))
        entries.append(_string_list_entry(rng, name, f"https://www.instagram.com/{handle}", ts))
    # One malformed record: string_list_data present but empty, no usable name at all.
    entries.append({"timestamp": meta_epoch_seconds(random_utc_timestamp(rng)), "string_list_data": []})
    # One record with an unparseable timestamp.
    name, _ = _pick_name(rng, persona)
    entries.append({
        "timestamp": MALFORMED_META_TIMESTAMP,
        "string_list_data": [{"href": "https://www.instagram.com/x", "value": mangle_meta_string(name), "timestamp": MALFORMED_META_TIMESTAMP}],
    })
    rng.shuffle(entries)
    return entries


def _generate_pages_liked(rng: random.Random, persona: Persona) -> list[dict]:
    entries = []
    for _ in range(max(4, persona.activity_count // 10)):
        name, _ = _pick_name(rng, persona)
        display_name = name + (BIO_SUFFIX_DA if rng.random() < 0.3 else "")
        ts = meta_epoch_seconds(random_utc_timestamp(rng))
        entries.append(_string_list_entry(rng, display_name, "https://www.facebook.com/", ts))
    return entries


def _generate_liked_posts(rng: random.Random, persona: Persona) -> list[dict]:
    entries = []
    for _ in range(persona.activity_count // 3):
        name, _ = _pick_name(rng, persona)
        ts = meta_epoch_seconds(random_utc_timestamp(rng))
        entries.append({
            "title": mangle_meta_string(name),
            "string_list_data": [{"href": f"https://www.instagram.com/p/{ts}/", "timestamp": ts}],
        })
    return entries


def _generate_search_history(rng: random.Random, persona: Persona) -> list[dict]:
    entries = []
    for _ in range(max(5, persona.activity_count // 6)):
        is_news = rng.random() < persona.news_share
        query = rng.choice(NEWS_SEARCH_QUERIES_DA if is_news else NON_NEWS_SEARCH_QUERIES_DA)
        ts = meta_epoch_seconds(random_utc_timestamp(rng))
        entries.append({
            "title": mangle_meta_string("Searched for " + query),
            "search_data": {"text": mangle_meta_string(query), "timestamp": ts},
        })
    return entries


def _generate_ad_topics(rng: random.Random, persona: Persona) -> list[dict]:
    n = 3 if persona.news_share > 0.5 else 1
    topics = rng.sample(AD_TOPICS_DA, k=min(n, len(AD_TOPICS_DA)))
    if "Nyheder" not in topics and persona.news_share > 0.5:
        topics[0] = "Nyheder"
    return [{"name": mangle_meta_string(t)} for t in topics]


def build_archive(persona: Persona, locale: str, seed: int) -> ArchiveContent:
    rng = random.Random(f"{seed}-meta-{persona.name}-{locale}")
    root = ROOTS[locale]
    paths = PATHS[locale]
    return {
        f"{root}/{paths['following']}": json_bytes({"relationships_following": _generate_following(rng, persona)}),
        f"{root}/{paths['pages_liked']}": json_bytes({"page_likes_v2": _generate_pages_liked(rng, persona)}),
        f"{root}/{paths['liked_posts']}": json_bytes({"likes_media_likes": _generate_liked_posts(rng, persona)}),
        f"{root}/{paths['saved_posts']}": json_bytes({"saved_saved_media": _generate_liked_posts(rng, persona)}),
        f"{root}/{paths['search_history']}": json_bytes({"searches_user_searches": _generate_search_history(rng, persona)}),
        f"{root}/{paths['ad_topics']}": json_bytes({"topics_your_topics": _generate_ad_topics(rng, persona)}),
    }
