# --------------------------------------------------------------------
# The news-donation demo's data donation flow.
#
# Structure follows Feldspar's own demo script.py: named step functions
# using `yield from`, FlushLogs between long steps, one retry loop
# around file selection. What's different is that this flow lets a
# participant donate from more than one platform in a single session
# (a real donor is unlikely to use only one), looping the platform
# picker until they choose to finish.
# --------------------------------------------------------------------

import json
import logging
import zipfile

import pandas as pd

import port.api.props as props
from port.api.commands import CommandSystemDonate, CommandSystemExit, CommandUIRender, FlushLogs
from port.donation import meta, tiktok, youtube
from port.donation.archive_utils import ExportFormatError
from port.donation.schema import metadata_row, summarize

logger = logging.getLogger(__name__)

EXTRACTORS = {
    "youtube": youtube.extract_data,
    "tiktok": tiktok.extract_data,
    "instagram": meta.extract_data,
}

# Plain, not bilingual: proper nouns read the same in Danish. Only UI
# copy around them needs translating.
PLATFORM_LABELS = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram / Facebook",
}

RECORD_COLUMNS = [
    "record_type", "timestamp_copenhagen", "channel_or_account",
    "is_news", "content_ref", "is_ad", "had_parse_error", "parser_version",
]

RECORD_HEADERS = {
    "record_type": props.Translatable({"en": "Type", "da": "Type"}),
    "timestamp_copenhagen": props.Translatable({"en": "Time (Copenhagen)", "da": "Tidspunkt (København)"}),
    "channel_or_account": props.Translatable({"en": "Channel / account", "da": "Kanal / konto"}),
    "is_news": props.Translatable({"en": "News source?", "da": "Nyhedskilde?"}),
    "content_ref": props.Translatable({"en": "What it points to", "da": "Hvad det peger på"}),
    "is_ad": props.Translatable({"en": "Ad?", "da": "Annonce?"}),
    "had_parse_error": props.Translatable({"en": "Could not be fully read", "da": "Kunne ikke læses fuldt ud"}),
    "parser_version": props.Translatable({"en": "Parser version", "da": "Parser-version"}),
}


######################
# Data donation flow #
######################

def process(data):
    sessionId = data.get("sessionId")
    locale = data.get("locale", "en")
    logger.info(f"user entered donation flow (locale={locale})")

    donated: set[str] = set()
    while True:
        platform = yield from step_select_platform(donated, locale)
        if platform is None:
            break
        yield FlushLogs

        records = yield from step_extract_platform(platform, locale)
        if records is not None:
            yield from step_consent(platform, sessionId, records, locale)
            donated.add(platform)

    yield exit(0, "donation flow finished")


def step_select_platform(donated: set[str], locale: str):
    remaining = [p for p in EXTRACTORS if p not in donated]
    if not remaining:
        return None

    labels = [PLATFORM_LABELS[p] for p in remaining]
    finish_label = "I'm done — finish" if locale != "da" else "Jeg er færdig"
    items = [{"id": i, "value": label} for i, label in enumerate(labels + [finish_label])]

    result = yield render_data_submission_page(prompt_select_platform(items, bool(donated), locale))
    if result.__type__ != "PayloadString":
        return None
    for platform, label in zip(remaining, labels):
        if result.value == label:
            return platform
    return None  # matched "finish", or nothing matched (shouldn't happen)


def step_extract_platform(platform: str, locale: str):
    extractor = EXTRACTORS[platform]
    while True:
        fileResult = yield render_data_submission_page(prompt_file(platform, locale))
        if fileResult.__type__ != "PayloadFile":
            return None
        try:
            with zipfile.ZipFile(fileResult.value) as zf:
                records = extractor(zf, locale)
        except ExportFormatError as e:
            retry = yield render_data_submission_page(retry_confirmation(str(e), locale))
            if retry.__type__ == "PayloadTrue":
                continue
            return None
        except (IOError, zipfile.BadZipFile):
            retry = yield render_data_submission_page(retry_confirmation(WRONG_FILE_TEXT[locale], locale))
            if retry.__type__ == "PayloadTrue":
                continue
            return None
        return records


def step_consent(platform: str, sessionId: str, records: list, locale: str):
    body = build_consent_body(platform, records, locale)
    result = yield render_data_submission_page(body)
    if result.__type__ == "PayloadJSON":
        yield donate(f"{sessionId}-{platform}", result.value)
    elif result.__type__ == "PayloadFalse":
        value = json.dumps({"status": "data_submission declined", "platform": platform})
        yield donate(f"{sessionId}-{platform}", value)


##########################
# Consent screen content #
##########################

def build_consent_body(platform: str, records: list, locale: str) -> list:
    """Everything shown before the donate/decline buttons: a plain-language
    summary, an explicit statement of what's excluded, and the exact rows
    that would be shared (editable/removable, per Feldspar's own table UI) —
    what's shown here IS what gets donated, nothing more."""
    summary = summarize(records)

    intro = props.PropsUIPromptText(
        title=props.Translatable({"en": "Review your data", "da": "Gennemgå dine data"}),
        text=props.Translatable(summary_text(platform, summary, locale)),
    )
    drop_statement = props.PropsUIPromptText(
        title=props.Translatable({"en": "What we don't collect", "da": "Hvad vi ikke indsamler"}),
        text=props.Translatable(DROP_STATEMENT_TEXT[platform]),
    )

    records_df = pd.DataFrame([{c: getattr(r, c) for c in RECORD_COLUMNS} for r in records], columns=RECORD_COLUMNS)
    records_table = props.PropsUIPromptConsentFormTable(
        "records", 1,
        props.Translatable({"en": "Your activity", "da": "Din aktivitet"}),
        props.Translatable({
            "en": "Every row below is exactly what would be donated. Remove any row you don't want to share.",
            "da": "Hver række nedenfor er præcis, hvad der ville blive doneret. Fjern enhver række, du ikke ønsker at dele.",
        }),
        records_df,
        headers=RECORD_HEADERS,
    )

    metadata_df = pd.DataFrame([metadata_row(platform)])
    metadata_table = props.PropsUIPromptConsentFormTable(
        "metadata", 2,
        props.Translatable({"en": "Technical version info", "da": "Teknisk versionsinfo"}),
        props.Translatable({
            "en": "Which version of the extraction logic produced the data above — lets a researcher tell donations processed by different logic apart.",
            "da": "Hvilken version af udtræksprocessen der producerede dataene ovenfor.",
        }),
        metadata_df,
    )

    buttons = props.PropsUIDataSubmissionButtons(
        donate_question=props.Translatable({
            "en": "Would you like to donate the data above?",
            "da": "Vil du donere dataene ovenfor?",
        }),
        donate_button=props.Translatable({"en": "Yes, donate", "da": "Ja, donér"}),
    )

    return [intro, drop_statement, records_table, metadata_table, buttons]


def summary_text(platform: str, summary: dict, locale: str) -> dict:
    by_type = ", ".join(f"{v} {k}" for k, v in summary["by_record_type"].items())
    en = (
        f"We found {summary['total_records']} records ({by_type}). "
        f"{summary['news_records']} were flagged as coming from a source on our news list. "
        f"{summary['parse_error_records']} record(s) could not be fully read and are marked below."
    )
    da = (
        f"Vi fandt {summary['total_records']} poster ({by_type}). "
        f"{summary['news_records']} blev markeret som kommende fra en kilde på vores nyhedsliste. "
        f"{summary['parse_error_records']} post(er) kunne ikke læses fuldt ud og er markeret nedenfor."
    )
    return {"en": en, "da": da}


DROP_STATEMENT_TEXT = {
    "youtube": {
        "en": "We do not collect video titles, video descriptions, or the full text of anything you searched for — only which channel a video belongs to, when you watched or searched, and whether that channel matched our news-source list.",
        "da": "Vi indsamler ikke videotitler, videobeskrivelser eller den fulde tekst af det, du har søgt efter — kun hvilken kanal en video tilhører, hvornår du så eller søgte, og om den kanal matchede vores nyhedskildeliste.",
    },
    "tiktok": {
        "en": "We do not collect video captions, comments, or profile bios. TikTok's own export does not include the creator's name on watch/like history, so those rows carry no channel information — only a link, a timestamp, and (for follows) the account you followed.",
        "da": "Vi indsamler ikke video-tekster, kommentarer eller profilbeskrivelser. TikToks eget dataudtræk indeholder ikke skaberens navn i se-/synes godt om-historik, så disse rækker indeholder ingen kanalinformation — kun et link, et tidspunkt og (for følger) den konto, du fulgte.",
    },
    "instagram": {
        "en": "We do not collect post captions, comment text, or message content. This only covers who you follow, which pages/posts you liked or saved, your search terms, and Meta's own inferred ad-interest topics — not your feed itself, which isn't included in a personal data export.",
        "da": "Vi indsamler ikke opslagstekster, kommentartekst eller beskedindhold. Dette dækker kun, hvem du følger, hvilke sider/opslag du har synes godt om eller gemt, dine søgeord og Metas egne udledte annonceinteresseemner — ikke selve din feed, som ikke er inkluderet i et personligt dataudtræk.",
    },
}

WRONG_FILE_TEXT = {
    "en": "We couldn't open that file as a zip archive. Please make sure you selected the export .zip file you downloaded, without unzipping it first.",
    "da": "Vi kunne ikke åbne den fil som et zip-arkiv. Sørg for, at du har valgt den .zip-eksportfil, du downloadede, uden at have udpakket den først.",
}


######################
# UI helpers         #
######################

def render_data_submission_page(body):
    header = props.PropsUIHeader(props.Translatable({
        "en": "News media diet — data donation",
        "da": "Nyhedsmediediæt — datadonation",
    }))
    body_items = [body] if not isinstance(body, list) else body
    page = props.PropsUIPageDataSubmission("news-donation", header, body_items)
    return CommandUIRender(page)


def prompt_select_platform(items, has_donated: bool, locale: str):
    if locale == "da":
        title = "Vælg en platform" if not has_donated else "Vil du donere fra en anden platform?"
        description = "Vælg, hvilken platforms dataeksport du vil donere fra."
    else:
        title = "Choose a platform" if not has_donated else "Donate from another platform?"
        description = "Choose which platform's data export you'd like to donate from."
    return props.PropsUIPromptRadioInput(
        title=props.Translatable({"en": title, "da": title}),
        description=props.Translatable({"en": description, "da": description}),
        items=items,
    )


def prompt_file(platform: str, locale: str):
    label = PLATFORM_LABELS[platform]
    en = f"Please select your {label} data export .zip file."
    da = f"Vælg din {label} dataeksport .zip-fil."
    return props.PropsUIPromptFileInput(props.Translatable({"en": en, "da": da}), "application/zip")


def retry_confirmation(message: str, locale: str):
    ok = props.Translatable({"en": "Try again", "da": "Prøv igen"})
    return props.PropsUIPromptConfirm(props.Translatable({"en": message, "da": message}), ok)


def donate(key, json_string):
    return CommandSystemDonate(key, json_string)


def exit(code, info):
    return CommandSystemExit(code, info)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3 or sys.argv[1] not in EXTRACTORS:
        print(f"Usage: python -m port.script <{'|'.join(EXTRACTORS)}> path/to/export.zip")
        sys.exit(1)
    with zipfile.ZipFile(sys.argv[2]) as zf:
        for record in EXTRACTORS[sys.argv[1]](zf, "en"):
            print(record)
