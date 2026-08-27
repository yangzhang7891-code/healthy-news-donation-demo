"""UTC to Europe/Copenhagen conversion.

Source timestamps across all three platforms are UTC (see the fixture
generator's timestamps.py for each platform's exact wire format). The
research question concerns a Danish media diet, so Copenhagen local
time — not UTC — is what the analysis needs.

Requires the IANA tzdata database, which Pyodide does not bundle with
the interpreter by default — "tzdata" must be added to py_worker.js's
loadPackage() list, or zoneinfo.ZoneInfoNotFoundError is raised at
import time in the browser (it works fine locally, where the OS
usually already has a tz database, which is exactly the kind of
works-here-breaks-there gap this note exists to head off).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

COPENHAGEN = ZoneInfo("Europe/Copenhagen")


def utc_to_copenhagen(dt: datetime) -> datetime:
    """Convert an aware or naive-and-assumed-UTC datetime to Europe/Copenhagen local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(COPENHAGEN)


def format_copenhagen(dt: datetime) -> str:
    return utc_to_copenhagen(dt).isoformat()
