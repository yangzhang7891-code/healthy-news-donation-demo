"""Turn an in-memory {path: content} mapping into a real .zip file.

Keeps the platform-specific generators focused on shaping realistic
export content; this module just handles packaging it the way a
participant would actually receive it from a "download your data"
button.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Union

ArchiveContent = dict[str, Union[str, bytes]]


def write_archive(contents: ArchiveContent, out_path: Path) -> None:
    """Write `contents` (archive-relative path -> text/bytes) to a zip file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in contents.items():
            if isinstance(data, str):
                data = data.encode("utf-8")
            zf.writestr(path, data)


def json_bytes(obj) -> bytes:
    """Serialize like a real export tool would: UTF-8 on disk, non-ASCII characters left as-is.

    `ensure_ascii=False` matters here: it's what makes Danish characters
    show up as actual UTF-8 bytes in the fixture rather than \\uXXXX
    escapes, which is what real export files look like (and is a
    precondition for the Meta mis-encoding bug to reproduce faithfully).
    """
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
