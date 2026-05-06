"""Tests for pmstate.reader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pmstate.envelope import Event
from pmstate.reader import ReaderError, read_events
from pmstate.writer import append_event


def _make_event(i: int) -> Event:
    return Event.new(
        type="pmstate.quote.received",
        source="/active/procurement/quotes",
        data={"i": i},
    )


def _seed(p: Path, n: int) -> list[Event]:
    events = [_make_event(i) for i in range(n)]
    for e in events:
        append_event(p, e)
    return events


def test_empty_file_yields_nothing(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    p.write_text("", encoding="utf-8")
    assert list(read_events(p)) == []


def test_read_all(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed(p, 10)
    rows = list(read_events(p))
    assert len(rows) == 10
    assert [r["data"]["i"] for r in rows] == list(range(10))


def test_limit_truncates(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed(p, 100)
    rows = list(read_events(p, limit=5))
    assert len(rows) == 5
    assert [r["data"]["i"] for r in rows] == [0, 1, 2, 3, 4]


def test_filter_excludes(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed(p, 10)
    rows = list(read_events(p, filter=lambda d: d["data"]["i"] % 2 == 0))
    assert [r["data"]["i"] for r in rows] == [0, 2, 4, 6, 8]


def test_byte_range_slice(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed(p, 10)
    raw = p.read_bytes()
    second_line_offset = raw.index(b"\n") + 1
    third_line_offset = raw.index(b"\n", second_line_offset) + 1
    rows = list(read_events(p, start=second_line_offset, end=third_line_offset))
    assert len(rows) == 1
    assert rows[0]["data"]["i"] == 1


def test_blank_lines_skipped(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    p.write_text(
        '{"id":"a","source":"/x","type":"pmstate.q.r","time":"t"}\n'
        "\n"
        '{"id":"b","source":"/x","type":"pmstate.q.r","time":"t"}\n',
        encoding="utf-8",
    )
    assert len(list(read_events(p))) == 2


def test_malformed_line_raises_with_context(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    p.write_text('{"ok":true}\n{not json}\n', encoding="utf-8")
    gen = read_events(p)
    next(gen)
    with pytest.raises(ReaderError) as exc:
        next(gen)
    assert exc.value.line_number == 2
    assert exc.value.path == p


def test_start_at_eof_yields_nothing(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed(p, 5)
    size = p.stat().st_size
    assert list(read_events(p, start=size)) == []


def test_filter_with_limit(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed(p, 100)
    rows = list(read_events(p, filter=lambda d: d["data"]["i"] >= 50, limit=3))
    assert len(rows) == 3
    assert [r["data"]["i"] for r in rows] == [50, 51, 52]


def test_registry_hook_applied(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed(p, 3)

    class _FakeRegistry:
        def upcast(self, d: dict[str, Any]) -> dict[str, Any]:
            return {**d, "upcasted": True}

    rows = list(read_events(p, registry=_FakeRegistry()))  # type: ignore[arg-type]
    assert all(r["upcasted"] is True for r in rows)
