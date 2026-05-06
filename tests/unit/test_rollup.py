"""Tests for pmstate.rollup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.rollup import compute_view
from pmstate.storage import Log, Table
from pmstate.writer import append_event


def _seed_log(path: Path, n: int) -> None:
    for i in range(n):
        append_event(
            path,
            Event.new(type="pmstate.q.r", source="/x", data={"i": i}),
        )


def test_leaf_with_state_no_view(tmp_path: Path) -> None:
    log_path = tmp_path / "log.jsonl"
    _seed_log(log_path, 3)
    leaf = Node("quotes", state=Log(log_path))
    out = compute_view(leaf, tmp_path)
    assert out["count"] == 3


def test_leaf_with_state_and_view(tmp_path: Path) -> None:
    log_path = tmp_path / "log.jsonl"
    _seed_log(log_path, 5)

    def sum_view(events: Any) -> dict[str, Any]:
        return {"sum": sum(e["data"]["i"] for e in events)}

    leaf = Node("x", state=Log(log_path), view=sum_view)
    assert compute_view(leaf, tmp_path) == {"sum": 0 + 1 + 2 + 3 + 4}


def test_leaf_with_table_and_view(tmp_path: Path) -> None:
    table_path = tmp_path / "t.json"
    table_path.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")

    def view(doc: Any) -> dict[str, Any]:
        return {"keys": sorted(doc.keys())}

    leaf = Node("vendors", state=Table(table_path), view=view)
    assert compute_view(leaf, tmp_path) == {"keys": ["a", "b"]}


def test_leaf_no_state(tmp_path: Path) -> None:
    leaf = Node("empty")
    assert compute_view(leaf, tmp_path) == {}


def test_internal_generic_dump(tmp_path: Path) -> None:
    log1 = tmp_path / "a.jsonl"
    log2 = tmp_path / "b.jsonl"
    _seed_log(log1, 1)
    _seed_log(log2, 2)
    parent = Node(
        "p",
        children=[Node("a", state=Log(log1)), Node("b", state=Log(log2))],
    )
    out = compute_view(parent, tmp_path)
    assert out["a"]["count"] == 1
    assert out["b"]["count"] == 2


def test_internal_with_reducer(tmp_path: Path) -> None:
    log1 = tmp_path / "a.jsonl"
    log2 = tmp_path / "b.jsonl"
    _seed_log(log1, 3)
    _seed_log(log2, 7)

    def reducer(children: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return {"total": children["a"]["count"] + children["b"]["count"]}

    parent = Node(
        "p",
        reducer=reducer,
        children=[Node("a", state=Log(log1)), Node("b", state=Log(log2))],
    )
    assert compute_view(parent, tmp_path) == {"total": 10}


def test_reducer_exception_becomes_error(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    _seed_log(log, 1)

    def bad(_children: dict[str, dict[str, Any]]) -> dict[str, Any]:
        raise RuntimeError("boom")

    parent = Node("p", reducer=bad, children=[Node("a", state=Log(log))])
    out = compute_view(parent, tmp_path)
    assert out["exception"] == "RuntimeError"
    assert out["error"] == "boom"


def test_cache_hit_does_not_recompute(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    _seed_log(log, 2)
    calls = {"n": 0}

    def reducer(children: dict[str, dict[str, Any]]) -> dict[str, Any]:
        calls["n"] += 1
        return {"v": children["a"]["count"]}

    parent = Node("p", reducer=reducer, children=[Node("a", state=Log(log))])
    (tmp_path / "p").mkdir(exist_ok=True)
    compute_view(parent, tmp_path, node_path="/p")
    compute_view(parent, tmp_path, node_path="/p")
    assert calls["n"] == 1


def test_cache_miss_after_child_change(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    _seed_log(log, 1)
    calls = {"n": 0}

    def reducer(children: dict[str, dict[str, Any]]) -> dict[str, Any]:
        calls["n"] += 1
        return {"v": children["a"]["count"]}

    parent = Node("p", reducer=reducer, children=[Node("a", state=Log(log))])
    (tmp_path / "p").mkdir(exist_ok=True)
    compute_view(parent, tmp_path, node_path="/p")
    _seed_log(log, 1)
    compute_view(parent, tmp_path, node_path="/p")
    assert calls["n"] == 2


def test_cache_file_lands_at_node_disk_path(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    _seed_log(log, 1)
    parent = Node("p", children=[Node("a", state=Log(log))])
    (tmp_path / "p").mkdir(exist_ok=True)
    compute_view(parent, tmp_path, node_path="/p")
    cache_file = tmp_path / "p" / ".pmstate" / "rollup.json"
    assert cache_file.exists()
    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    assert "key" in cached
    assert "view" in cached
