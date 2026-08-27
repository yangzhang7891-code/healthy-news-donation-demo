"""Synthetic export-archive generator for the data donation demo.

Everything under this package produces *fake* data only — no real
platform access, no real accounts, no real personal data. It exists so
the extraction scripts in `port/donation/` can be developed and tested
without ever touching a real export.

This package is intentionally kept outside `port/` (the package that
gets built into the browser wheel) so none of this generator code or
its bundled name lists end up shipped to participants.
"""
