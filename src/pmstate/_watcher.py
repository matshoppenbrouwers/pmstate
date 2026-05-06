"""Internal filesystem watcher. Fires a callback when files under ``root`` change."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path

from watchfiles import Change
from watchfiles import watch as wf_watch


def _is_wsl_mount(root: Path) -> bool:
    realpath = os.path.realpath(root)
    return realpath.startswith("/mnt/")


def watch(
    root: Path,
    on_change: Callable[[set[Path]], None],
    *,
    force_polling: bool | None = None,
    stop_event: threading.Event | None = None,
) -> threading.Thread:
    """Spawn a daemon thread that fires ``on_change(paths)`` on each filesystem event.

    On WSL2 ``/mnt/...`` paths, polling is forced unless ``force_polling`` is set
    explicitly. ``stop_event`` lets callers cleanly shut the thread down.
    """
    use_polling = force_polling if force_polling is not None else _is_wsl_mount(root)
    stop = stop_event or threading.Event()

    def _run() -> None:
        for changes in wf_watch(
            str(root),
            force_polling=use_polling,
            stop_event=stop,
        ):
            on_change({Path(p) for _change, p in _normalise(changes)})

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def _normalise(changes: set[tuple[Change, str]]) -> set[tuple[Change, str]]:
    return changes
