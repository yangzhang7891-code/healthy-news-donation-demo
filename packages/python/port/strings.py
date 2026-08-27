"""Centralized UI string table for the donation flow.

Every piece of participant-facing text and its Danish translation
lives here, in one place — same "auditable in one review, not
scattered through code" reasoning as the news allowlist
(port/config/news_allowlist.yaml). script.py pulls text through t(),
never builds a Translatable inline, so a translator or reviewer can
read this one file top to bottom instead of hunting through the flow
logic for hardcoded copy.

Tone: plain and calm, not marketed — a data donation flow describing
what it does, not selling it. No exclamation marks, no "amazing",
no urgency language.
"""

from __future__ import annotations

import port.api.props as props

STRINGS: dict[str, dict[str, str]] = {
    "header_title": {
        "en": "News media diet — data donation",
        "da": "Nyhedsmediediæt — datadonation",
    },
    "platform_picker_title_first": {
        "en": "Choose a platform",
        "da": "Vælg en platform",
    },
    "platform_picker_title_again": {
        "en": "Donate from another platform?",
        "da": "Vil du donere fra en anden platform?",
    },
    "platform_picker_description": {
        "en": "Choose which platform's data export you'd like to donate from.",
        "da": "Vælg, hvilken platforms dataeksport du vil donere fra.",
    },
    "finish_label": {
        "en": "I'm done — finish",
        "da": "Jeg er færdig",
    },
    "file_prompt": {
        "en": "Please select your {label} data export .zip file.",
        "da": "Vælg din {label} dataeksport .zip-fil.",
    },
    "wrong_file": {
        "en": "We couldn't open that file as a zip archive. Please make sure you selected the export .zip file you downloaded, without unzipping it first.",
        "da": "Vi kunne ikke åbne den fil som et zip-arkiv. Sørg for, at du har valgt den .zip-eksportfil, du downloadede, uden at have udpakket den først.",
    },
    "retry_try_again": {
        "en": "Try again",
        "da": "Prøv igen",
    },
    "consent_title": {
        "en": "Review your data",
        "da": "Gennemgå dine data",
    },
    "drop_title": {
        "en": "What we don't collect",
        "da": "Hvad vi ikke indsamler",
    },
    "drop_youtube": {
        "en": "We do not collect video titles, video descriptions, or the full text of anything you searched for — only which channel a video belongs to, when you watched or searched, and whether that channel matched our news-source list.",
        "da": "Vi indsamler ikke videotitler, videobeskrivelser eller den fulde tekst af det, du har søgt efter — kun hvilken kanal en video tilhører, hvornår du så eller søgte, og om den kanal matchede vores nyhedskildeliste.",
    },
    "drop_tiktok": {
        "en": "We do not collect video captions, comments, or profile bios. TikTok's own export does not include the creator's name on watch/like history, so those rows carry no channel information — only a link, a timestamp, and (for follows) the account you followed.",
        "da": "Vi indsamler ikke video-tekster, kommentarer eller profilbeskrivelser. TikToks eget dataudtræk indeholder ikke skaberens navn i se-/synes godt om-historik, så disse rækker indeholder ingen kanalinformation — kun et link, et tidspunkt og (for følger) den konto, du fulgte.",
    },
    "drop_instagram": {
        "en": "We do not collect post captions, comment text, or message content. This only covers who you follow, which pages/posts you liked or saved, your search terms, and Meta's own inferred ad-interest topics — not your feed itself, which isn't included in a personal data export.",
        "da": "Vi indsamler ikke opslagstekster, kommentartekst eller beskedindhold. Dette dækker kun, hvem du følger, hvilke sider/opslag du har synes godt om eller gemt, dine søgeord og Metas egne udledte annonceinteresseemner — ikke selve din feed, som ikke er inkluderet i et personligt dataudtræk.",
    },
    "records_table_title": {
        "en": "Your activity",
        "da": "Din aktivitet",
    },
    "records_table_description": {
        "en": "Every row below is exactly what would be donated. Remove any row you don't want to share.",
        "da": "Hver række nedenfor er præcis, hvad der ville blive doneret. Fjern enhver række, du ikke ønsker at dele.",
    },
    "metadata_table_title": {
        "en": "Technical version info",
        "da": "Teknisk versionsinfo",
    },
    "metadata_table_description": {
        "en": "Which version of the extraction logic produced the data above — lets a researcher tell donations processed by different logic apart.",
        "da": "Hvilken version af udtræksprocessen der producerede dataene ovenfor.",
    },
    "donate_question": {
        "en": "Would you like to donate the data above?",
        "da": "Vil du donere dataene ovenfor?",
    },
    "donate_button": {
        "en": "Yes, donate",
        "da": "Ja, donér",
    },
    "col_record_type": {"en": "Type", "da": "Type"},
    "col_timestamp": {"en": "Time (Copenhagen)", "da": "Tidspunkt (København)"},
    "col_channel": {"en": "Channel / account", "da": "Kanal / konto"},
    "col_is_news": {"en": "News source?", "da": "Nyhedskilde?"},
    "col_content_ref": {"en": "What it points to", "da": "Hvad det peger på"},
    "col_is_ad": {"en": "Ad?", "da": "Annonce?"},
    "col_had_error": {"en": "Could not be fully read", "da": "Kunne ikke læses fuldt ud"},
    "col_parser_version": {"en": "Parser version", "da": "Parser-version"},
    "summary_text": {
        "en": "We found {total} records ({by_type}). {news} were flagged as coming from a source on our news list. {errors} record(s) could not be fully read and are marked below.",
        "da": "Vi fandt {total} poster ({by_type}). {news} blev markeret som kommende fra en kilde på vores nyhedsliste. {errors} post(er) kunne ikke læses fuldt ud og er markeret nedenfor.",
    },
    "html_export_error": {
        "en": "This export looks like it was downloaded in HTML format. Please re-request your {label} export with 'JSON' selected as the output format — see the printable instructions for exactly where that setting is.",
        "da": "Dette eksport ser ud til at være downloadet i HTML-format. Anmod venligst om din {label}-eksport igen med 'JSON' valgt som outputformat — se de trykte instruktioner for præcis, hvor den indstilling er.",
    },
}

# Proper nouns: identical in both languages, kept out of STRINGS since
# there's nothing to translate.
PLATFORM_LABELS = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram / Facebook",
}


def t(key: str, **fmt: str) -> props.Translatable:
    """Look up a string table entry and wrap it as a Translatable, formatting each locale's text if fmt is given."""
    entry = STRINGS[key]
    if fmt:
        entry = {locale: text.format(**fmt) for locale, text in entry.items()}
    return props.Translatable(entry)


def plain(key: str, locale: str, **fmt: str) -> str:
    """Look up a string table entry and return the plain string for one locale — for text that ends up inside a
    DataFrame cell or an f-string rather than a Translatable (e.g. retry_confirmation's message argument)."""
    entry = STRINGS[key]
    text = entry.get(locale, entry["en"])
    return text.format(**fmt) if fmt else text
