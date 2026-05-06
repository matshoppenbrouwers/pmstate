"""Tests for pmstate.node."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import attrs.exceptions
import pytest

from pmstate._paths import NodePathError
from pmstate.node import Node
from pmstate.storage import Log, Table


def test_node_minimal() -> None:
    n = Node("active")
    assert n.name == "active"
    assert n.state is None
    assert n.view is None
    assert n.reducer is None
    assert n.children == ()


def test_node_empty_name_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Node("")


def test_node_name_with_slash_rejected() -> None:
    with pytest.raises(ValueError, match="must not contain"):
        Node("a/b")


def test_node_children_iterable_frozen_to_tuple(tmp_path: Path) -> None:
    n = Node("p", children=[Node("a"), Node("b")])
    assert isinstance(n.children, tuple)
    assert tuple(c.name for c in n.children) == ("a", "b")


def test_node_duplicate_sibling_names_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate sibling name"):
        Node("p", children=[Node("a"), Node("a")])


def test_node_is_frozen() -> None:
    n = Node("a")
    with pytest.raises(attrs.exceptions.FrozenInstanceError):
        n.name = "b"  # type: ignore[misc]


def test_node_view_must_be_callable() -> None:
    with pytest.raises(TypeError, match="callable"):
        Node("a", view="not callable")  # type: ignore[arg-type]


def test_node_reducer_must_be_callable() -> None:
    with pytest.raises(TypeError, match="callable"):
        Node("a", reducer=42)  # type: ignore[arg-type]


def test_find_root() -> None:
    root = Node("active", children=[Node("procurement")])
    assert root.find("/") is root
    assert root.find("") is root


def test_find_direct_child() -> None:
    child = Node("procurement")
    root = Node("active", children=[child])
    assert root.find("/procurement") is child


def test_find_deep() -> None:
    quotes = Node("quotes")
    proc = Node("procurement", children=[quotes])
    root = Node("active", children=[proc])
    assert root.find("/procurement/quotes") is quotes


def test_find_miss_raises() -> None:
    root = Node("active", children=[Node("procurement")])
    with pytest.raises(NodePathError, match="no child named"):
        root.find("/nope")


def test_find_invalid_path_raises() -> None:
    root = Node("a")
    with pytest.raises(NodePathError):
        root.find("missing-leading-slash")


def test_effective_description_explicit() -> None:
    n = Node("a", description="explicit one")
    assert n.effective_description == "explicit one"


def test_effective_description_from_view_doc() -> None:
    def my_view(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """First line.

        Second line ignored.
        """
        return {}

    n = Node("a", view=my_view)
    assert n.effective_description == "First line."


def test_effective_description_none() -> None:
    assert Node("a").effective_description is None


def test_effective_description_view_no_doc() -> None:
    def view(_events: Iterable[dict[str, Any]]) -> dict[str, Any]:
        return {}

    assert Node("a", view=view).effective_description is None


def test_node_with_state(tmp_path: Path) -> None:
    log = Log(tmp_path / "x.jsonl")
    n = Node("quotes", state=log)
    assert n.state is log


def test_procurement_subtree_constructs(tmp_path: Path) -> None:
    proc = Node(
        "procurement",
        children=[
            Node("quotes", state=Log(tmp_path / "quotes.jsonl")),
            Node("lpos", state=Log(tmp_path / "lpos.jsonl")),
            Node("vendors", state=Table(tmp_path / "vendors.json")),
        ],
    )
    assert proc.find("/quotes").name == "quotes"
    assert proc.find("/vendors").name == "vendors"
