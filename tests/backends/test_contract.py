"""Backend-agnostic contract suite for StorageBackend implementations.

Parametrized over a ``backend`` fixture covering FilesystemBackend (on disk)
and FakeMemoryBackend (dict-backed). A future Supabase/Anvil backend slots in
by adding one fixture param.
"""

from __future__ import annotations

from typing import Any

import pytest

from pmstate.backends import FilesystemBackend, StorageBackend
from tests.backends.conftest import FakeMemoryBackend


@pytest.fixture(params=["filesystem", "memory"])
def backend(request: pytest.FixtureRequest, tmp_path: Any) -> StorageBackend:
    if request.param == "filesystem":
        return FilesystemBackend(tmp_path)
    if request.param == "memory":
        return FakeMemoryBackend()
    raise ValueError(f"unknown backend param: {request.param}")


STREAM = "events.jsonl"


def _event(i: int) -> dict[str, Any]:
    return {"type": "pmstate.test.event", "data": {"i": i}}


def test_append_read_round_trip(backend: StorageBackend) -> None:
    e = _event(0)
    backend.append(STREAM, e)
    assert list(backend.read(STREAM)) == [e]


def test_read_preserves_order(backend: StorageBackend) -> None:
    events = [_event(i) for i in range(100)]
    for e in events:
        backend.append(STREAM, e)
    got = list(backend.read(STREAM))
    assert [e["data"]["i"] for e in got] == list(range(100))


def test_after_cursor_resumes(backend: StorageBackend) -> None:
    c0 = backend.append(STREAM, _event(0))
    backend.append(STREAM, _event(1))
    backend.append(STREAM, _event(2))
    got = list(backend.read(STREAM, after=c0))
    assert [e["data"]["i"] for e in got] == [1, 2]


def test_until_bound(backend: StorageBackend) -> None:
    backend.append(STREAM, _event(0))
    c1 = backend.append(STREAM, _event(1))
    backend.append(STREAM, _event(2))
    got = list(backend.read(STREAM, until=c1))
    assert [e["data"]["i"] for e in got] == [0, 1]


def test_after_and_until_window(backend: StorageBackend) -> None:
    c0 = backend.append(STREAM, _event(0))
    backend.append(STREAM, _event(1))
    c2 = backend.append(STREAM, _event(2))
    backend.append(STREAM, _event(3))
    got = list(backend.read(STREAM, after=c0, until=c2))
    assert [e["data"]["i"] for e in got] == [1, 2]


def test_limit_caps_results(backend: StorageBackend) -> None:
    for i in range(10):
        backend.append(STREAM, _event(i))
    got = list(backend.read(STREAM, limit=3))
    assert [e["data"]["i"] for e in got] == [0, 1, 2]


def test_post_decode_filter(backend: StorageBackend) -> None:
    for i in range(10):
        backend.append(STREAM, _event(i))
    evens = [e for e in backend.read(STREAM) if e["data"]["i"] % 2 == 0]
    assert [e["data"]["i"] for e in evens] == [0, 2, 4, 6, 8]


def test_empty_stream_yields_nothing(backend: StorageBackend) -> None:
    assert list(backend.read("never-written.jsonl")) == []
