"""Hypothesis property tests for the four agent tools' bound invariants."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.storage import Log
from pmstate.tools import find_state, list_tree, read_log
from pmstate.tree import Tree
from pmstate.writer import append_event


def _build_tree(root_dir: Path, n_quotes: int) -> Tree:
    log = root_dir / "active" / "procurement" / "quotes" / "log.jsonl"
    for i in range(n_quotes):
        append_event(log, Event.new(type="pmstate.q.r", source="/x", data={"i": i}))
    return Tree(
        "alpha",
        root=Node(
            "active",
            children=[
                Node(
                    "procurement",
                    children=[Node("quotes", state=Log(log))],
                ),
            ],
        ),
    )


@given(
    n=st.integers(min_value=0, max_value=20),
    limit=st.integers(min_value=1, max_value=1000),
)
@settings(max_examples=30, deadline=None)
def test_read_log_never_exceeds_limit(n: int, limit: int) -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        tree = _build_tree(root, n)
        rows = read_log(tree, "/procurement/quotes", root, limit=limit)
        assert len(rows) <= limit
        assert len(rows) <= n


@given(
    max_results=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=20, deadline=None)
def test_find_state_never_exceeds_max_results(max_results: int) -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        tree = _build_tree(root, 5)
        rows = find_state(tree, "count", root_dir=root, max_results=max_results)
        assert len(rows) <= max_results


@given(depth=st.integers(min_value=1, max_value=3))
@settings(max_examples=10, deadline=None)
def test_list_tree_depth_invariant(depth: int) -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        tree = _build_tree(root, 1)
        rows = list_tree(tree, "/", depth=depth)
        for r in rows:
            segments = [s for s in r["path"].split("/") if s]
            assert len(segments) <= depth
