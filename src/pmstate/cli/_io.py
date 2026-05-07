"""Atomic, refuse-on-collision file writing for the CLI."""

from __future__ import annotations

import os
from pathlib import Path


def write_file_safe(path: Path, contents: str, *, force: bool = False) -> None:
    """Write ``contents`` to ``path`` atomically. Refuses on collision unless ``force``."""
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(contents, encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
