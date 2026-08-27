# Healthy News — a data donation demo

A working demo of a GDPR Article 15 data donation flow for measuring
news exposure in personalised media diets, built on
[Feldspar](https://github.com/eyra/feldspar) (Eyra's current tool for
data donation apps; the older `eyra/port` is deprecated).

**▶ Try it: <https://yangzhang7891-code.github.io/healthy-news-donation-demo/>**

A participant brings a data export from YouTube, TikTok, Instagram or
Facebook. Everything is parsed **in their own browser**, via Python
compiled to WebAssembly — no export file is ever uploaded. They see
exactly which rows would be shared, can delete any of them, and only
then decide whether to donate.

You don't need an export of your own to try it: the landing page links
four synthetic sample files, including a deliberately wrong-format one
so you can watch the JSON-vs-HTML detection fire. On the live demo,
"donate" hands the JSON back to you as a download — there is no server
and nothing is transmitted anywhere. The first load takes a few
seconds while Pyodide downloads.

> **This is a portfolio piece, not production software.** No ethics
> approval, no real participants, no validated classifier. Everything
> here is developed and tested against synthetic fixtures — there is
> no real personal data in this repository, and there never should be.
>
> Two constraints worth stating up front, because they bound what
> this data can support: watch history records what was *watched*,
> not everything that was *recommended*; and Meta exports show diet
> **supply** (who you follow) rather than **exposure** (what the feed
> actually showed you). A fuller `LIMITATIONS.md` is still to be
> written.

Full documentation — the GDPR basis, the privacy design, and how to
run it — is being written up separately. Start with
[MONITORING.md](MONITORING.md) for how the extraction code is kept
honest, and the worked example below for why that matters.

---

## Worked example: catching a silent schema break

This is the failure mode the whole test setup exists for, so it's
worth showing rather than asserting. The sequence below is real, and
the commits are in the history in this order.

**The premise.** A platform ships an update. YouTube's watch history
used to identify the channel like this:

```json
"subtitles": [{"name": "DR Nyheder", "url": "https://youtube.com/channel/UC..."}]
```

and now does it like this:

```json
"channel": {"name": "DR Nyheder", "url": "https://youtube.com/channel/UC..."}
```

A rename plus a shape change — a video has exactly one channel, so
collapsing the list is a tidy-up an engineer makes without thinking
about anyone downstream. Nothing announces it.

**Step 1 — what the old parser does.** It keeps working. That is the
problem. Running it against the changed export:

| signal | healthy export | changed export | different? |
| --- | --- | --- | --- |
| exception raised | none | none | no |
| total records | 152 | 152 | no |
| counts by record type | 122 watch / 30 search | 122 watch / 30 search | no |
| parse errors | 2 | 2 | no |
| timestamps populated | 98.7% | 98.7% | no |
| **channel name populated** | **95.9%** | **0.0%** | **yes** |
| **records classified as news** | **90** | **0** | **yes** |

Every donation collected after this update would look complete and
arrive with the study's main variable empty. Worse than missing: every
donor would look like a *committed news avoider*, which is a plausible
finding rather than an obvious error.

**Step 2 — the canary catches it.** Not because it checked for this
change, which nobody could have anticipated, but because it asserts on
the data rather than on the absence of exceptions:

```
FF.

AssertionError: youtube/schema_v2_news_heavy_en.zip:
  'channel_or_account' populated in only 0.0% of watch records
  (floor 85%, was 96% at baseline). A field this empty usually means
  the platform renamed or moved it — see MONITORING.md.
assert 0.0 >= 0.85

assert 0 == 90     # news classification count
```

The `.` at the end of `FF.` is the point of the exercise: the third
assertion — **record counts against baseline — passed**. A canary that
only counted rows would have reported this export as healthy.

**Step 3 — the fix.** The parser learns to read the channel from
either shape, rather than migrating to the new one: donations already
collected came from v1 exports, and donors receive whichever format the
platform gives them. `PARSER_VERSION` is bumped 1.0.0 → 1.1.0, which
is what lets a researcher months later separate donations parsed by the
broken logic from ones parsed by the fixed logic, instead of pooling
them and averaging a real signal against an artefact.

**Step 4 — what stays broken.** Teaching the parser this rename does
not make it immune to the next one. So the demonstration in
`tests/test_schema_break.py` was kept alive against a rename the parser
has *not* been taught, because that is the honest general case. The
parser is not what protects the dataset from an unknown future change —
the canary is.

**The lesson.** A parser that crashes gets fixed the same day; someone
sees a crash. A parser that returns the right number of rows and an
empty column can run for an entire collection period. That asymmetry
is the argument for asserting on extraction counts *and* field-fill
rates, and for running them on a schedule rather than only on push.

Reproduce it:

```bash
cd packages/python && poetry run pytest tests/test_schema_break.py -v
```

---

## Repository layout

| Path | What's in it |
| --- | --- |
| `packages/python/port/donation/` | One extractor per platform, plus the shared record schema |
| `packages/python/port/config/` | The news-source allowlist — the auditable "counts as news" decision |
| `packages/python/port/strings.py` | Every participant-facing string, Danish and English |
| `packages/python/fixtures/` | The synthetic export generator and its committed archives |
| `packages/python/tests/` | Per-parser tests, the canary, and the worked example above |
| `docs/export-instructions.html` | Printable A4 sheet telling donors how to request each export |
| `MONITORING.md` | What breaks, how you find out, what to do |
| `docs/feldspar-upstream.md` | Upstream Feldspar's own README, kept for API reference |

## Running the tests

```bash
cd packages/python && poetry install --with test && poetry run pytest tests/ -v
```

## Running the app

```bash
pnpm install && pnpm run start
```

Then open http://localhost:3000.

## Attribution and licence

This is a derivative of [eyra/feldspar](https://github.com/eyra/feldspar),
retaining its full commit history and its **AGPL-3.0** licence — so this
repository is AGPL-3.0 too, and any network deployment of it (including
the hosted demo above) has to keep its source available. That's the
reason the repository is public, not merely a convenience.

Upstream Feldspar is by Eyra, funded by UU, PDI-SSH
([D3i](https://datadonation.eu/)) and Eyra. Its own README is preserved
at [docs/feldspar-upstream.md](docs/feldspar-upstream.md).

What this repository adds on top of upstream: the three platform
extractors and their record schema, the synthetic fixture generator,
the news-source allowlist, the bilingual string table and kiosk
language picker, the canary and its CI, the printable instruction
sheet, and two accessibility fixes plus a `bridge` seam in the
framework itself (`RadioItem` keyboard operability, `radiogroup`
semantics, and `ScriptHostComponent`'s optional `bridge` prop) that
would be reasonable to send upstream.
