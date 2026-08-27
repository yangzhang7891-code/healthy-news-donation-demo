# --------------------------------------------------------------------
# The news-donation demo's data donation flow.
#
# Structure follows Feldspar's own demo script.py: named step functions
# using `yield from`, FlushLogs between long steps, one retry loop
# around file selection. What's different is that this flow lets a
# participant donate from more than one platform in a single session
# (a real donor is unlikely to use only one), looping the platform
# picker until they choose to finish.
#
# All participant-facing copy is pulled from port/strings.py via t()/
# plain() — see that module for the actual English/Danish text.
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
from port.strings import PLATFORM_LABELS, plain, t

logger = logging.getLogger(__name__)

EXTRACTORS = {
    "youtube": youtube.extract_data,
    "tiktok": tiktok.extract_data,
    "instagram": meta.extract_data,
}

RECORD_COLUMNS = [
    "record_type", "timestamp_copenhagen", "channel_or_account",
    "is_news", "content_ref", "is_ad", "had_parse_error", "parser_version",
]

RECORD_HEADERS = {
    "record_type": t("col_record_type"),
    "timestamp_copenhagen": t("col_timestamp"),
    "channel_or_account": t("col_channel"),
    "is_news": t("col_is_news"),
    "content_ref": t("col_content_ref"),
    "is_ad": t("col_is_ad"),
    "had_parse_error": t("col_had_error"),
    "parser_version": t("col_parser_version"),
}

DROP_STATEMENT_KEY = {
    "youtube": "drop_youtube",
    "tiktok": "drop_tiktok",
    "instagram": "drop_instagram",
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
    finish_label = plain("finish_label", locale)
    items = [{"id": i, "value": label} for i, label in enumerate(labels + [finish_label])]

    result = yield render_data_submission_page(prompt_select_platform(items, bool(donated)))
    if result.__type__ != "PayloadString":
        return None
    for platform, label in zip(remaining, labels):
        if result.value == label:
            return platform
    return None  # matched "finish", or nothing matched (shouldn't happen)


def step_extract_platform(platform: str, locale: str):
    extractor = EXTRACTORS[platform]
    label = PLATFORM_LABELS[platform]
    while True:
        fileResult = yield render_data_submission_page(prompt_file(platform))
        if fileResult.__type__ != "PayloadFile":
            return None
        try:
            with zipfile.ZipFile(fileResult.value) as zf:
                records = extractor(zf, locale)
        except ExportFormatError:
            retry = yield render_data_submission_page(retry_confirmation(plain("html_export_error", locale, label=label)))
            if retry.__type__ == "PayloadTrue":
                continue
            return None
        except (IOError, zipfile.BadZipFile):
            retry = yield render_data_submission_page(retry_confirmation(plain("wrong_file", locale)))
            if retry.__type__ == "PayloadTrue":
                continue
            return None
        return records


def step_consent(platform: str, sessionId: str, records: list, locale: str):
    body = build_consent_body(platform, records)
    result = yield render_data_submission_page(body)
    if result.__type__ == "PayloadJSON":
        yield donate(f"{sessionId}-{platform}", result.value)
    elif result.__type__ == "PayloadFalse":
        value = json.dumps({"status": "data_submission declined", "platform": platform})
        yield donate(f"{sessionId}-{platform}", value)


##########################
# Consent screen content #
##########################

def build_consent_body(platform: str, records: list) -> list:
    """Everything shown before the donate/decline buttons: a plain-language
    summary, an explicit statement of what's excluded, and the exact rows
    that would be shared (editable/removable, per Feldspar's own table UI) —
    what's shown here IS what gets donated, nothing more."""
    summary = summarize(records)

    intro = props.PropsUIPromptText(title=t("consent_title"), text=t("summary_text", **summary_fmt(summary)))
    drop_statement = props.PropsUIPromptText(title=t("drop_title"), text=t(DROP_STATEMENT_KEY[platform]))

    records_df = pd.DataFrame([{c: getattr(r, c) for c in RECORD_COLUMNS} for r in records], columns=RECORD_COLUMNS)
    records_table = props.PropsUIPromptConsentFormTable(
        "records", 1,
        t("records_table_title"),
        t("records_table_description"),
        records_df,
        headers=RECORD_HEADERS,
    )

    metadata_df = pd.DataFrame([metadata_row(platform)])
    metadata_table = props.PropsUIPromptConsentFormTable(
        "metadata", 2,
        t("metadata_table_title"),
        t("metadata_table_description"),
        metadata_df,
    )

    buttons = props.PropsUIDataSubmissionButtons(donate_question=t("donate_question"), donate_button=t("donate_button"))

    return [intro, drop_statement, records_table, metadata_table, buttons]


def summary_fmt(summary: dict) -> dict:
    """String-table `{...}` placeholders for summary_text: total/news/errors counts, plus a "N type, M type" breakdown."""
    return {
        "total": str(summary["total_records"]),
        "news": str(summary["news_records"]),
        "errors": str(summary["parse_error_records"]),
        "by_type": ", ".join(f"{v} {k}" for k, v in summary["by_record_type"].items()),
    }


######################
# UI helpers         #
######################

def render_data_submission_page(body):
    header = props.PropsUIHeader(t("header_title"))
    body_items = [body] if not isinstance(body, list) else body
    page = props.PropsUIPageDataSubmission("news-donation", header, body_items)
    return CommandUIRender(page)


def prompt_select_platform(items, has_donated: bool):
    title_key = "platform_picker_title_again" if has_donated else "platform_picker_title_first"
    return props.PropsUIPromptRadioInput(
        title=t(title_key),
        description=t("platform_picker_description"),
        items=items,
    )


def prompt_file(platform: str):
    return props.PropsUIPromptFileInput(t("file_prompt", label=PLATFORM_LABELS[platform]), "application/zip")


def retry_confirmation(message: str):
    return props.PropsUIPromptConfirm(props.Translatable({"en": message, "da": message}), t("retry_try_again"))


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
