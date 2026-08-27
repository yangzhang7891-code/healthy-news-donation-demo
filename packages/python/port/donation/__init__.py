"""Per-platform data extraction for the news-donation demo.

One module per platform (youtube.py, tiktok.py, meta.py), each
exposing an `extract_data(zf, locale) -> list[DonationRecord]`
function that follows the same structure Feldspar's own demo
script.py uses: open the archive, locate the relevant files by
content shape (never by hardcoded path — see archive_utils.py),
normalize into the shared record schema (schema.py), and flag news
items against the allowlist (news_sources.py).
"""
