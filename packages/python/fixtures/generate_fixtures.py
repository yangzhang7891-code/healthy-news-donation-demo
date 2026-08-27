"""CLI entry point: generate every synthetic fixture archive.

Usage:
    python -m fixtures.generate_fixtures --seed 42 --out fixtures/archives

Deterministic given --seed (each generator seeds its own random.Random
from a string derived from the seed, platform, persona, and locale) —
re-running with the same seed regenerates byte-identical archives.
Re-run this whenever a generator module changes, and commit the
resulting archives: Phase 4's tests and canary run against what's
committed here, not against a live run of this script, so the fixture
files are themselves the artifact under version control.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fixtures import meta, tiktok, youtube
from fixtures.archive_builder import write_archive
from fixtures.personas import PERSONAS

LOCALES = ["en", "da"]


def generate_all(seed: int, out_dir: Path) -> list[Path]:
    written: list[Path] = []

    def emit(path: Path, contents: dict) -> None:
        write_archive(contents, path)
        written.append(path)

    for persona in PERSONAS.values():
        for locale in LOCALES:
            emit(out_dir / "youtube" / f"{persona.name}_{locale}.zip",
                 youtube.build_archive(persona, locale, seed))
            emit(out_dir / "tiktok" / f"old_{persona.name}_{locale}.zip",
                 tiktok.build_old_schema_archive(persona, locale, seed))
            emit(out_dir / "tiktok" / f"new_{persona.name}_{locale}.zip",
                 tiktok.build_new_schema_archive(persona, locale, seed))
            emit(out_dir / "meta" / f"{persona.name}_{locale}.zip",
                 meta.build_archive(persona, locale, seed))

    for locale in LOCALES:
        emit(out_dir / "youtube" / f"paused_empty_{locale}.zip",
             youtube.build_paused_history_archive(locale, missing=False))
        emit(out_dir / "youtube" / f"paused_missing_{locale}.zip",
             youtube.build_paused_history_archive(locale, missing=True))

    emit(out_dir / "youtube" / "html_export.zip", youtube.build_html_export_archive(seed))

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "archives")
    args = parser.parse_args()

    written = generate_all(args.seed, args.out)
    total_bytes = sum(p.stat().st_size for p in written)
    print(f"Generated {len(written)} fixture archives ({total_bytes / 1024:.1f} KiB) in {args.out}")
    for p in sorted(written):
        print(f"  {p.relative_to(args.out.parent)}  ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
