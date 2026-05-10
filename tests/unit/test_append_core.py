"""Tests for ``pmstate.cli._append.prepare_append`` shared validation core."""

from __future__ import annotations

from pathlib import Path

import pytest

from pmstate.cli._append import AppendPlan, normalise_type, prepare_append
from pmstate.cli._spec import EventSchema, Spec
from pmstate.node import Node
from pmstate.storage import Log, Table
from pmstate.tree import Tree


@pytest.fixture
def spec() -> Spec:
    events = {
        "quote.received": EventSchema(
            fields={"vendor": "str", "amount": "int", "currency": "str"}
        ),
        "quote.cancelled": EventSchema(fields={"vendor": "str", "reason": "str"}),
    }
    return Spec(name="x", pmstate_version="0.3.0", root="root", nodes=(), events=events)


@pytest.fixture
def tree(tmp_path: Path) -> Tree:
    quotes_log = Log(path=tmp_path / "state" / "quotes.jsonl")
    table_node = Node(name="reference", state=Table(path=tmp_path / "state" / "ref.json"))
    quotes_node = Node(name="quotes", state=quotes_log)
    procurement = Node(name="procurement", children=(quotes_node, table_node))
    root = Node(name="root", children=(procurement,))
    return Tree(name="proc", root=root)


def test_normalise_type_adds_prefix() -> None:
    assert normalise_type("quote.received") == "pmstate.quote.received"


def test_normalise_type_preserves_prefix() -> None:
    assert normalise_type("pmstate.quote.received") == "pmstate.quote.received"


def test_happy_path_unprefixed_type(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec,
        tree,
        "/procurement/quotes",
        "quote.received",
        {"vendor": "acme", "amount": 100, "currency": "USD"},
    )
    assert plan.issues == ()
    assert plan.log_path is not None
    assert plan.log_path.name == "quotes.jsonl"
    assert plan.event is not None
    assert plan.event.type == "pmstate.quote.received"
    assert plan.event.source == "/procurement/quotes"
    assert plan.event.data == {"vendor": "acme", "amount": 100, "currency": "USD"}


def test_happy_path_prefixed_type(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec,
        tree,
        "/procurement/quotes",
        "pmstate.quote.received",
        {"vendor": "acme", "amount": 100, "currency": "USD"},
    )
    assert plan.issues == ()
    assert plan.event is not None
    assert plan.event.type == "pmstate.quote.received"


def test_unknown_path(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/nonexistent", "quote.received", {"vendor": "x", "amount": 1, "currency": "USD"}
    )
    assert plan.log_path is None
    assert plan.event is None
    assert len(plan.issues) == 1
    assert "/nonexistent" in plan.issues[0].msg


def test_non_log_leaf(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/reference", "quote.received",
        {"vendor": "x", "amount": 1, "currency": "USD"},
    )
    assert plan.log_path is None
    assert any("state=Table" in i.msg or "state=table" in i.msg.lower() for i in plan.issues)


def test_unknown_event_type_with_suggestion(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/quotes", "quote.recieved",  # typo
        {"vendor": "x", "amount": 1, "currency": "USD"},
    )
    assert plan.log_path is None
    assert any("did you mean" in i.msg for i in plan.issues)
    assert any("quote.received" in i.msg for i in plan.issues)


def test_unknown_data_key(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/quotes", "quote.received",
        {"vendor": "x", "amount": 1, "currency": "USD", "extra": "junk"},
    )
    assert any("'extra'" in i.msg for i in plan.issues)


def test_missing_required_data_key(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/quotes", "quote.received",
        {"vendor": "x", "amount": 1},  # missing currency
    )
    assert any("missing required data key 'currency'" in i.msg for i in plan.issues)


def test_wrong_type_data_value(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/quotes", "quote.received",
        {"vendor": "x", "amount": "not-an-int", "currency": "USD"},
    )
    assert any("data field 'amount'" in i.msg for i in plan.issues)


def test_oversize_event(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/quotes", "quote.received",
        {"vendor": "x" * 5000, "amount": 1, "currency": "USD"},
    )
    assert plan.log_path is None
    assert any("exceeds" in i.msg and "ceiling" in i.msg for i in plan.issues)


def test_overrides_propagate(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/quotes", "quote.received",
        {"vendor": "x", "amount": 1, "currency": "USD"},
        source="/manual",
        subject="quote-1",
        causationid="abc-123",
    )
    assert plan.event is not None
    assert plan.event.source == "/manual"
    assert plan.event.subject == "quote-1"
    assert plan.event.causationid == "abc-123"


def test_appendplan_as_dict_shape(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/quotes", "quote.received",
        {"vendor": "x", "amount": 1, "currency": "USD"},
    )
    out = plan.as_dict()
    assert isinstance(out["log_path"], str)
    assert isinstance(out["event"], dict)
    assert out["issues"] == []


def test_appendplan_as_dict_failure(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(spec, tree, "/nope", "quote.received", {})
    out = plan.as_dict()
    assert out["log_path"] is None
    assert out["event"] is None
    assert len(out["issues"]) == 1


def test_returns_AppendPlan_type(spec: Spec, tree: Tree) -> None:
    plan = prepare_append(
        spec, tree, "/procurement/quotes", "quote.received",
        {"vendor": "x", "amount": 1, "currency": "USD"},
    )
    assert isinstance(plan, AppendPlan)
