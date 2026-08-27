"""Bundled pool of plausible Danish channel/account names for fixtures.

Mixes real, well-known Danish news outlets with invented non-news
names so persona-driven generation produces a realistic mix of
watched/followed content. The outlet names are real (used only as
text labels in synthetic records — no real activity is attached to
them); the non-news names are made up.

Outlet list matches the seven named in the project brief (2026-08-27):
DR Nyheder, TV 2 Nyhederne, Politiken, Berlingske, Ekstra Bladet,
Zetland, Information. This same list should seed the human-auditable
news allowlist built in Phase 2 (`port/config/news_allowlist.yaml`) —
keep them in sync by hand; they're deliberately not generated from
each other, since the allowlist is a research decision and this file
is just test data that happens to reuse the same outlet names.
"""

NEWS_CHANNELS_DA = [
    "DR Nyheder",
    "TV 2 Nyhederne",
    "Politiken",
    "Berlingske",
    "Ekstra Bladet",
    "Zetland",
    "Information",
]

# Lowercase, space-free handles for platforms (TikTok, Instagram) where
# account names look like handles rather than display names.
NEWS_HANDLES_DA = {
    "DR Nyheder": "drnyheder",
    "TV 2 Nyhederne": "tv2nyhederne",
    "Politiken": "politiken",
    "Berlingske": "berlingske",
    "Ekstra Bladet": "ekstrabladet",
    "Zetland": "zetland_dk",
    "Information": "information_dk",
}

NON_NEWS_CHANNELS_DA = [
    # music
    "Musikvideo Danmark",
    "Lars & Bandet",
    "Popstjernen",
    # gaming
    "Gamer Nikolaj",
    "Spilzonen",
    "Retro Spil DK",
    # cooking
    "Mormors Køkken",
    "Nem Mad Hver Dag",
    "Bagværk med Marie",
    # sport
    "Fodboldkanalen",
    "Håndbold Danmark",
    "Cykelsport DK",
]

NON_NEWS_HANDLES_DA = {
    "Musikvideo Danmark": "musikvideodk",
    "Lars & Bandet": "larsogbandet",
    "Popstjernen": "popstjernen",
    "Gamer Nikolaj": "gamernikolaj",
    "Spilzonen": "spilzonen",
    "Retro Spil DK": "retrospildk",
    "Mormors Køkken": "mormorskoekken",
    "Nem Mad Hver Dag": "nemmadhverdag",
    "Bagværk med Marie": "bagvaerkmedmarie",
    "Fodboldkanalen": "fodboldkanalen",
    "Håndbold Danmark": "haandbolddanmark",
    "Cykelsport DK": "cykelsportdk",
}

# A handful of Danish search queries, some news-shaped, some not — used
# for search-history fixtures. Kept short since search history is a
# free-text field in real exports, not a controlled vocabulary.
NEWS_SEARCH_QUERIES_DA = [
    "dr nyheder direkte",
    "seneste nyt ukraine",
    "folketingsvalg meningsmåling",
    "politiken kommentar",
]

NON_NEWS_SEARCH_QUERIES_DA = [
    "opskrift på boller",
    "fodbold resultater i dag",
    "bedste guitar solo",
    "playstation 5 tilbud",
]
