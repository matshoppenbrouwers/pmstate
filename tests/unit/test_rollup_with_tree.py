"""Integration: rollup cache invalidation across spawn/prune."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.rollup import compute_view_at
from pmstate.storage import Log
from pmstate.tree import Tree
from pmstate.writer import append_event


def _seed(p: Path, n: int) -> None:
    for i in range(n):
        append_event(p, Event.new(type="pmstate.q.r", source="/x", data={"i": i}))


def _make_tree(tmp_path: Path, count: int = 1) -> Tree:
    log = tmp_path / "active" / "procurement" / "quotes" / "log.jsonl"
    _seed(log, count)
    quotes = Node("quotes", state=Log(log))
    procurement = Node("procurement", children=[quotes])
    return Tree("alpha", root=Node("active", children=[procurement]))


def test_compute_view_at_root(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path, 3)
    out = compute_view_at(tree, "/", tmp_path)
    assert out["procurement"]["quotes"]["count"] == 3


def test_compute_view_at_subpath(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path, 5)
    out = compute_view_at(tree, "/procurement", tmp_path)
    assert out["quotes"]["count"] == 5


def test_cache_persists_at_node_disk_location(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path, 1)
    compute_view_at(tree, "/procurement", tmp_path)
    cache = tmp_path / "procurement" / ".pmstate" / "rollup.json"
    assert cache.exists()


def test_spawn_invalidates_parent_cache(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path, 1)
    out1 = compute_view_at(tree, "/procurement", tmp_path)
    assert "lpos" not in out1

    new_log = tmp_path / "active" / "procurement" / "lpos" / "log.jsonl"
    _seed(new_log, 2)
    tree2 = tree.spawn("/procurement", Node("lpos", state=Log(new_log)))
    out2 = compute_view_at(tree2, "/procurement", tmp_path)
    assert "lpos" in out2
    assert out2["lpos"]["count"] == 2


def test_prune_invalidates_parent_cache(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path, 1)
    extra_log = tmp_path / "active" / "procurement" / "lpos" / "log.jsonl"
    _seed(extra_log, 2)
    tree2 = tree.spawn("/procurement", Node("lpos", state=Log(extra_log)))
    out_before = compute_view_at(tree2, "/procurement", tmp_path)
    assert "lpos" in out_before

    tree3 = tree2.prune("/procurement/lpos")
    out_after = compute_view_at(tree3, "/procurement", tmp_path)
    assert "lpos" not in out_after


def test_sibling_change_does_not_invalidate_unrelated_branch(tmp_path: Path) -> None:
    log_a = tmp_path / "a" / "log.jsonl"
    log_b = tmp_path / "b" / "log.jsonl"
    _seed(log_a, 2)
    _seed(log_b, 5)
    calls = {"a": 0, "b": 0}

    def reducer_a(children: dict[str, dict[str, Any]]) -> dict[str, Any]:
        calls["a"] += 1
        return {"a_total": children["leaf"]["count"]}

    def reducer_b(children: dict[str, dict[str, Any]]) -> dict[str, Any]:
        calls["b"] += 1
        return {"b_total": children["leaf"]["count"]}

    tree = Tree(
        "x",
        root=Node(
            "root",
            children=[
                Node("a", reducer=reducer_a, children=[Node("leaf", state=Log(log_a))]),
                Node("b", reducer=reducer_b, children=[Node("leaf", state=Log(log_b))]),
            ],
        ),
    )

    compute_view_at(tree, "/a", tmp_path)
    compute_view_at(tree, "/b", tmp_path)
    assert calls == {"a": 1, "b": 1}

    _seed(log_a, 1)
    compute_view_at(tree, "/a", tmp_path)
    compute_view_at(tree, "/b", tmp_path)
    assert calls == {"a": 2, "b": 1}
