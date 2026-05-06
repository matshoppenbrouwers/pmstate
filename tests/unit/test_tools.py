"""Tests for pmstate.tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.storage import Log, Table
from pmstate.tools import ToolError, find_state, get_state, list_tree, read_log
from pmstate.tree import Tree
from pmstate.writer import append_event


def _seed(p: Path, n: int) -> None:
    for i in range(n):
        append_event(p, Event.new(type="pmstate.q.r", source="/x", data={"i": i}))


def _build(tmp_path: Path) -> Tree:
    quotes_log = tmp_path / "active" / "procurement" / "quotes" / "log.jsonl"
    lpos_log = tmp_path / "active" / "procurement" / "lpos" / "log.jsonl"
    _seed(quotes_log, 3)
    _seed(lpos_log, 2)
    return Tree(
        "alpha",
        root=Node(
            "active",
            description="Top-level active work.",
            children=[
                Node(
                    "procurement",
                    description="Vendor quotes, LPOs.",
                    children=[
                        Node("quotes", state=Log(quotes_log)),
                        Node("lpos", state=Log(lpos_log)),
                    ],
                ),
            ],
        ),
    )


# ---- list_tree ----


def test_list_tree_root_depth_1(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    out = list_tree(tree, "/")
    assert len(out) == 1
    assert out[0]["name"] == "procurement"
    assert out[0]["has_children"] is True
    assert out[0]["type"] == "internal"


def test_list_tree_depth_2(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    out = list_tree(tree, "/", depth=2)
    names = [r["name"] for r in out]
    assert names == ["procurement", "quotes", "lpos"]


def test_list_tree_leaf_metadata(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    out = list_tree(tree, "/procurement")
    quotes = next(r for r in out if r["name"] == "quotes")
    assert quotes["type"] == "leaf"
    assert quotes["has_state"] is True
    assert quotes["has_children"] is False
    assert quotes["path"] == "/procurement/quotes"


def test_list_tree_depth_out_of_range(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    with pytest.raises(ValueError, match="depth must be"):
        list_tree(tree, "/", depth=0)
    with pytest.raises(ValueError, match="depth must be"):
        list_tree(tree, "/", depth=4)


def test_list_tree_empty_node(tmp_path: Path) -> None:
    tree = Tree("x", root=Node("empty"))
    assert list_tree(tree, "/") == []


# ---- get_state ----


def test_get_state_root(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    out = get_state(tree, "/", tmp_path)
    assert out["procurement"]["quotes"]["count"] == 3


def test_get_state_leaf(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    out = get_state(tree, "/procurement/quotes", tmp_path)
    assert out["count"] == 3


def test_get_state_missing_path_returns_error(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    out = get_state(tree, "/nope", tmp_path)
    assert out["exception"] == "NodePathError"


# ---- find_state ----


def test_find_state_substring(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    matches = find_state(tree, "count", root_dir=tmp_path)
    assert any("/quotes" in m["path"] for m in matches)


def test_find_state_max_results_capped(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    matches = find_state(tree, "count", root_dir=tmp_path, max_results=1)
    assert len(matches) <= 1


def test_find_state_max_results_out_of_range(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    with pytest.raises(ValueError, match="max_results"):
        find_state(tree, "x", root_dir=tmp_path, max_results=0)
    with pytest.raises(ValueError, match="max_results"):
        find_state(tree, "x", root_dir=tmp_path, max_results=10_000)


def test_find_state_path_glob(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    matches = find_state(tree, "count", root_dir=tmp_path, path_glob="*quotes*")
    assert all("quotes" in m["path"] for m in matches)
    assert matches


def test_find_state_no_matches(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    assert find_state(tree, "definitely-not-there", root_dir=tmp_path) == []


# ---- read_log ----


def test_read_log_returns_events(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    rows = read_log(tree, "/procurement/quotes", tmp_path)
    assert len(rows) == 3
    assert [r["data"]["i"] for r in rows] == [0, 1, 2]


def test_read_log_limit(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    rows = read_log(tree, "/procurement/quotes", tmp_path, limit=2)
    assert len(rows) == 2


def test_read_log_filter(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    rows = read_log(
        tree,
        "/procurement/quotes",
        tmp_path,
        filter=lambda d: d["data"]["i"] > 0,
    )
    assert [r["data"]["i"] for r in rows] == [1, 2]


def test_read_log_on_non_log_state_raises(tmp_path: Path) -> None:
    table_path = tmp_path / "v.json"
    table_path.write_text("{}", encoding="utf-8")
    tree = Tree("x", root=Node("vendors", state=Table(table_path)))
    with pytest.raises(ToolError, match="does not have a Log state"):
        read_log(tree, "/", tmp_path)


def test_read_log_on_internal_node_raises(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    with pytest.raises(ToolError):
        read_log(tree, "/procurement", tmp_path)


def test_read_log_limit_out_of_range(tmp_path: Path) -> None:
    tree = _build(tmp_path)
    with pytest.raises(ValueError, match="limit"):
        read_log(tree, "/procurement/quotes", tmp_path, limit=0)
    with pytest.raises(ValueError, match="limit"):
        read_log(tree, "/procurement/quotes", tmp_path, limit=10_000)


def test_read_log_relative_path_resolves_under_root(tmp_path: Path) -> None:
    rel = Path("rel" / Path("log.jsonl"))
    abs_path = tmp_path / rel
    _seed(abs_path, 1)
    tree = Tree("x", root=Node("a", state=Log(rel)))
    rows: list[Any] = read_log(tree, "/", tmp_path)
    assert len(rows) == 1
