# Monitoring: what breaks, how you find out, what to do

This document is for whoever maintains the extraction code while a
donation study is running. It assumes no prior contact with this
repository.

The short version: **the failure worth worrying about is silent.** A
parser that crashes gets fixed the same day, because somebody sees a
crash. A parser that keeps running and quietly returns empty channel
names can survive an entire collection period, and you only discover
it at analysis, when the donations are already gathered and the donors
have gone home.

Everything below exists to shorten the time between "the data went
wrong" and "somebody knew".

---

## 1. How extraction breaks

Roughly in order of how likely it is to go unnoticed.

### A field gets renamed or moved (the dangerous one)

A platform renames `subtitles` to `creators`, or nests it one level
deeper. The parser still finds the file, still reads every record,
still returns the right number of rows — and every channel name is
now `None`.

Nothing raises. Row counts are unchanged. The donation looks complete.
What's actually happened is that the study's main variable is empty,
and because `is_news` is computed from the channel name, every donor
now looks like a total news avoider.

This is the failure this whole setup is built around. Concretely,
simulating exactly this break against a healthy fixture:

| signal | healthy | after `subtitles` → `creators` | caught? |
| --- | --- | --- | --- |
| total records | 152 | 152 | no |
| counts by record type | identical | identical | no |
| parse-error count | 2 | 2 | no |
| **records flagged as news** | **90** | **0** | **yes** |
| **channel fill rate** | **95.9%** | **0.0%** | **yes** |

A canary that only counted rows would have passed this cleanly.

### A file moves, or the export layout changes

TikTok did this already: older exports put everything in one nested
JSON, newer ones split it into one file per category. Both are
handled, and there's a test asserting they produce identical output.

This one is comparatively loud: if a file can no longer be located,
the count for that category drops to zero and the canary's count
assertions fire immediately.

### The export becomes localised in a new way

Folder and file names inside these archives are translated. This is
why nothing in the extraction code matches on a path — files are
found by inspecting what's *inside* them. If a platform introduced a
locale we hadn't considered, content-shape matching should still
work, which is the point of doing it that way.

### The export format silently changes to HTML

Donors pick a format when requesting an export, and HTML is often the
default. All three extractors detect this and raise a specific error
telling the participant to re-request as JSON, rather than returning
an empty result that looks like "you have no history".

### Character encoding corruption

Meta's export writer mis-encodes UTF-8 as latin-1, so Danish `æ`, `ø`,
`å` arrive mangled. This is fixed on read. It's dangerous for the same
reason as a renamed field: a mangled name doesn't crash anything, it
just stops matching the news allowlist and under-counts news exposure.

### Our own changes

The most frequent cause of a canary failure, in practice, is not a
platform at all. It's a well-intentioned edit to the extraction code
that changes output as a side effect.

---

## 2. How you find out

### The canary

`packages/python/tests/test_canary.py`. Run it directly:

```bash
cd packages/python && poetry run pytest tests/test_canary.py -v
```

It asserts two things that a "did it crash?" check cannot:

- **Extraction counts** for every committed fixture, against a
  recorded baseline. Catches records disappearing or appearing.
- **Field-fill rates** — the share of records where a field is
  actually populated, scoped to the record types that are supposed to
  carry it. Catches a field going empty while the row count is
  unchanged.

The scoping matters. A fill rate averaged over all records would be
diluted by record types that legitimately lack the field (TikTok watch
rows never carry a channel name), pushing the floor so low it could no
longer detect anything.

### When it runs

- On every push and pull request.
- **Every Monday at 06:00 UTC**, on a schedule.

The weekly run is the one that matters for fieldwork. Schema changes
don't arrive with a commit; the repository can sit untouched for a
month while a study collects. A scheduled run puts a date on the
problem.

### What this does and does not prove

Worth being blunt about, because it is easy to over-read a green tick:

The canary runs against **committed synthetic fixtures**. It reliably
catches regressions *we* introduce. It does **not** watch the real
platforms. A green canary means "extraction behaves as it did when the
baseline was recorded" — not "YouTube hasn't changed its export".

A real platform change is caught when someone re-requests a real
export, notices the shape differs, and updates the fixtures. The
canary then makes the consequences of that change explicit and
reviewable. Closing this gap properly needs a periodic real export
from a project-controlled test account, which is the honest next step
if this ever moves past a demo.

---

## 3. What to do when it fires

### Step 1 — read which assertion failed

The two kinds of failure mean different things:

- **Count mismatch** — records appeared or vanished. Usually a file
  is no longer found, or is found twice.
- **Fill-rate floor breached** — records are still being read, but a
  field is empty. Almost always a renamed or moved field. This is the
  serious one.

Failure messages name the fixture, the field, the observed rate and
the baseline.

### Step 2 — decide which of three things happened

1. **You changed extraction on purpose.** Adding a record type or
   fixing a bug legitimately changes the numbers.
2. **You changed extraction by accident.** A refactor altered output
   as a side effect. This is what the canary is best at catching.
3. **A platform changed its export.** The fixtures were updated from a
   new real export, and the parser hasn't caught up.

`git log` on `packages/python/port/donation/` and on
`packages/python/fixtures/` usually separates these in under a minute.

### Step 3 — act

**If the change was intended**, update `BASELINE` (and `FILL_FLOORS`
if a legitimate rate moved) in `test_canary.py`, and say *in the commit
message* which of the three cases it was. A baseline updated without
explanation is indistinguishable from a schema break that got
rubber-stamped — that note is the entire audit trail.

**If it was accidental**, fix the code, not the baseline.

**If a platform changed**, then in order:

1. Fix the parser so it handles both the old and the new shape.
   Donations already collected were produced by the old logic and
   still need to parse.
2. Add a fixture for the new shape and a regression test for it.
3. **Bump `PARSER_VERSION`** in
   `packages/python/port/donation/schema.py`. Every record and every
   donation payload carries this. Bumping it is what lets a
   researcher, months later, separate donations parsed by the broken
   logic from ones parsed by the fixed logic — instead of silently
   pooling them.
4. Update `BASELINE` to the corrected numbers.

### Step 4 — decide about the data already collected

This is a research decision, not a technical one, and it's the reason
`PARSER_VERSION` exists.

If a break ran undetected for some period, donations collected in that
window may be missing a variable. Because every record carries its
parser version, you can identify exactly which ones, and then choose
to re-parse the stored raw donations if you kept them, exclude the
affected window, or report the gap. What you must not do is analyse
the pooled set as if it were uniform.

---

## 4. Things this setup does not cover

Stated plainly so nobody assumes otherwise:

- **No live platform monitoring.** See the section above.
- **No alerting.** A failed scheduled run shows up in GitHub Actions.
  Nobody is paged. For a real study, wire the workflow's failure to
  wherever the team actually looks.
- **No validation that the fixtures resemble current real exports.**
  They encode what the schemas looked like when they were written
  (2026-08-27), and the TikTok and Meta shapes were never verified
  against a real export at all.
- **A known blind spot in YouTube detection**: a watch-history file
  containing nothing but removed/private-video stubs carries no signal
  distinguishing it from search history, and is not detected. Tested
  and documented in `test_youtube_extraction.py`.
- **Local tests and the browser run different pandas versions.** The
  browser uses whatever Pyodide bundles (1.5.3); local tests use
  pandas 3.x, because pandas 1.x has no wheel for the Python version
  this project targets. Anything touching a DataFrame needs a real
  in-browser check, not just a green pytest run.
