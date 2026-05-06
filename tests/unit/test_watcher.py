"""Tests for pmstate._watcher."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

from pmstate._watcher import _is_wsl_mount, watch


def test_callback_fires_on_file_create(tmp_path: Path) -> None:
    received: list[set[Path]] = []
    ready = threading.Event()

    def on_change(paths: set[Path]) -> None:
        received.append(paths)
        ready.set()

    stop = threading.Event()
    watch(tmp_path, on_change, force_polling=True, stop_event=stop)
    time.sleep(0.3)
    (tmp_path / "x.txt").write_text("hi", encoding="utf-8")

    assert ready.wait(timeout=5.0), "watcher callback did not fire within 5s"
    stop.set()
    assert any(p.name == "x.txt" for paths in received for p in paths)


def test_wsl_detection_true() -> None:
    with patch("pmstate._watcher.os.path.realpath", return_value="/mnt/c/foo"):
        assert _is_wsl_mount(Path("/mnt/c/foo")) is True


def test_wsl_detection_false() -> None:
    with patch("pmstate._watcher.os.path.realpath", return_value="/home/user"):
        assert _is_wsl_mount(Path("/home/user")) is False


def test_force_polling_overrides_auto_detect(tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    real_watch = __import__("watchfiles").watch

    def fake_watch(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        kwargs["stop_event"].set()  # type: ignore[union-attr]
        return real_watch(*args, **kwargs)

    stop = threading.Event()
    with patch("pmstate._watcher.wf_watch", side_effect=fake_watch):
        thread = watch(tmp_path, lambda _: None, force_polling=True, stop_event=stop)
        thread.join(timeout=2.0)

    assert captured.get("force_polling") is True
