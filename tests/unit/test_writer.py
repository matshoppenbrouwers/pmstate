"""Tests for pmstate.writer."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from pmstate.envelope import Event
from pmstate.writer import EventTooLargeError, append_event


def _make_event(i: int = 0) -> Event:
    return Event.new(
        type="pmstate.quote.received",
        source="/active/procurement/quotes",
        data={"i": i},
    )


def test_append_creates_parent_dir(tmp_path: Path) -> None:
    p = tmp_path / "deep" / "nested" / "log.jsonl"
    append_event(p, _make_event())
    assert p.exists()


def test_append_writes_one_line(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    e = _make_event()
    append_event(p, e)
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == e.to_dict()


def test_append_1000_events_preserves_order(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    events = [_make_event(i) for i in range(1000)]
    for e in events:
        append_event(p, e)
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1000
    decoded = [json.loads(line) for line in lines]
    assert [d["data"]["i"] for d in decoded] == list(range(1000))


def test_oversized_event_rejected(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    big = _make_event()
    big = Event.new(
        type=big.type,
        source=big.source,
        data={"x": "a" * 5000},
    )
    with pytest.raises(EventTooLargeError) as exc:
        append_event(p, big)
    assert exc.value.size > 4000


def test_fsync_no_error(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    append_event(p, _make_event(), fsync=True)
    assert p.exists()


def test_threaded_appends_dont_tear_lines(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"

    def worker(start: int) -> None:
        for i in range(start, start + 100):
            append_event(p, _make_event(i))

    threads = [threading.Thread(target=worker, args=(i * 100,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1000
    for line in lines:
        json.loads(line)
