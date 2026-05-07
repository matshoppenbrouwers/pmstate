"""Project root discovery: walk up looking for ``pmstate.yaml``."""

from __future__ import annotations

from pathlib import Path

PROJECT_MARKER = "pmstate.yaml"


def find_project_root(start: Path) -> Path | None:
    """Walk up from ``start`` to the first directory containing ``pmstate.yaml``.

    Returns ``None`` if no marker is found before reaching the filesystem root.
    """
    current = start.resolve()
    if current.is_file():
        current = current.parent
    while True:
        if (current / PROJECT_MARKER).is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent
