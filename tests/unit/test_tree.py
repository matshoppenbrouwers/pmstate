"""Tests for pmstate.tree."""

from __future__ import annotations

import attrs.exceptions
import pytest

from pmstate._paths import NodePathError
from pmstate.node import Node
from pmstate.tree import Tree


def _build() -> Tree:
    return Tree(
        "alpha",
        root=Node("active", children=[Node("procurement", children=[Node("quotes")])]),
    )


def test_get_root_and_descendants() -> None:
    t = _build()
    assert t.get("/").name == "active"
    assert t.get("/procurement").name == "procurement"
    assert t.get("/procurement/quotes").name == "quotes"


def test_spawn_at_root() -> None:
    t = _build()
    t2 = t.spawn("/", Node("invoicing"))
    assert t2 is not t
    assert tuple(c.name for c in t2.root.children) == ("procurement", "invoicing")
    assert tuple(c.name for c in t.root.children) == ("procurement",)


def test_spawn_deep() -> None:
    t = _build()
    t2 = t.spawn("/procurement", Node("vendors"))
    assert t2.get("/procurement/vendors").name == "vendors"


def test_spawn_duplicate_sibling_rejected() -> None:
    t = _build()
    with pytest.raises(ValueError, match="duplicate sibling name"):
        t.spawn("/", Node("procurement"))


def test_spawn_missing_parent_path() -> None:
    t = _build()
    with pytest.raises(NodePathError):
        t.spawn("/nope", Node("x"))


def test_prune_leaf() -> None:
    t = _build()
    t2 = t.prune("/procurement/quotes")
    assert t2.get("/procurement").children == ()


def test_prune_subtree() -> None:
    t = _build()
    t2 = t.prune("/procurement")
    assert t2.root.children == ()


def test_prune_root_rejected() -> None:
    t = _build()
    with pytest.raises(NodePathError, match="cannot prune the root"):
        t.prune("/")


def test_prune_missing_rejected() -> None:
    t = _build()
    with pytest.raises(NodePathError):
        t.prune("/nope")


def test_spawn_then_prune_round_trip() -> None:
    t = _build()
    new_node = Node("vendors")
    t2 = t.spawn("/procurement", new_node)
    t3 = t2.prune("/procurement/vendors")
    assert t3.get("/procurement").children == t.get("/procurement").children


def test_tree_is_frozen() -> None:
    t = _build()
    with pytest.raises(attrs.exceptions.FrozenInstanceError):
        t.name = "other"  # type: ignore[misc]
