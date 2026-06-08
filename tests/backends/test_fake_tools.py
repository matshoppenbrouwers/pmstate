"""Drive all four agent tools through FakeMemoryBackend with zero disk I/O.

This is the proof that the StorageBackend seam is real: ``list_tree``,
``get_state``, ``find_state``, and ``read_log`` all operate against an
in-memory backend, and ``tmp_path`` stays empty throughout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pmstate.backends import StorageBackend
from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.storage import Log
from pmstate.tools import find_state, get_state, list_tree, read_log
from pmstate.tree import Tree
from tests.backends.conftest import FakeMemoryBackend

LOG_STREAM = "events.jsonl"


def test_fake_satisfies_storage_backend_protocol() -> None:
    assert isinstance(FakeMemoryBackend(), StorageBackend)


def _count_reducer(children: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(children)}


def _build_tree() -> Tree:
    return Tree(
        "feedback",
        root=Node(
            "feedback",
            children=[
                Node(
                    "summary",
                    reducer=_count_reducer,
                    children=[Node("web"), Node("mobile")],
                ),
                Node("events", state=Log(Path(LOG_STREAM))),
            ],
        ),
    )


def _seed_log(backend: FakeMemoryBackend, n: int) -> None:
    for i in range(n):
        event = Event.new(type="pmstate.feedback.received", source="/events", data={"i": i})
        backend.append(LOG_STREAM, event.to_dict())


def test_four_tools_run_entirely_in_memory(tmp_path: Path) -> None:
    backend = FakeMemoryBackend()
    tree = _build_tree()
    _seed_log(backend, 3)

    # list_tree — pure tree walk, no backend involved.
    children = list_tree(tree, "/")
    assert {c["name"] for c in children} == {"summary", "events"}

    # get_state — reducer result routed through the backend cache.
    view = get_state(tree, "/summary", backend)
    assert view == {"count": 2}

    # find_state — scans the summary subtree, matching the reduced view.
    matches = find_state(tree, "2", root_dir=backend, path_glob="/summary*")
    assert [m["path"] for m in matches] == ["/summary"]

    # read_log — events read straight from the in-memory stream.
    rows = read_log(tree, "/events", backend)
    assert [r["data"]["i"] for r in rows] == [0, 1, 2]

    # The seam is real: the cache landed in memory and nothing hit disk.
    assert backend.read_cache("/summary") is not None
    assert list(tmp_path.iterdir()) == []
