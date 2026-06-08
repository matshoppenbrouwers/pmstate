"""Filesystem-specific behavior for FilesystemBackend (cursor format, layout)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pmstate.backends import FilesystemBackend
from pmstate.backends.filesystem import ReaderError

STREAM = "events.jsonl"


def _event(i: int) -> dict[str, Any]:
    return {"type": "pmstate.test.event", "data": {"i": i}}


def test_cursor_is_stringified_int(tmp_path: Path) -> None:
    backend = FilesystemBackend(tmp_path)
    cursor = backend.append(STREAM, _event(0))
    assert isinstance(cursor, str)
    assert int(cursor) == (tmp_path / STREAM).stat().st_size


def test_read_nonexistent_path_is_empty(tmp_path: Path) -> None:
    backend = FilesystemBackend(tmp_path)
    assert list(backend.read("absent/log.jsonl")) == []


def test_append_creates_only_the_log_file(tmp_path: Path) -> None:
    backend = FilesystemBackend(tmp_path)
    backend.append(STREAM, _event(0))
    assert [p.name for p in tmp_path.iterdir()] == [STREAM]
    assert not (tmp_path / ".pmstate").exists()


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    backend = FilesystemBackend(tmp_path)
    backend.append(STREAM, _event(0))
    with (tmp_path / STREAM).open("a", encoding="utf-8") as f:
        f.write("\n\n")
    backend.append(STREAM, _event(1))
    got = list(backend.read(STREAM))
    assert [e["data"]["i"] for e in got] == [0, 1]


def test_malformed_line_raises_reader_error(tmp_path: Path) -> None:
    backend = FilesystemBackend(tmp_path)
    (tmp_path / STREAM).write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ReaderError):
        list(backend.read(STREAM))


def test_stream_maps_to_nested_path(tmp_path: Path) -> None:
    backend = FilesystemBackend(tmp_path)
    backend.append("a/b/c.jsonl", _event(0))
    assert (tmp_path / "a" / "b" / "c.jsonl").exists()
