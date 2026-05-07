"""Tests for the pmstate public API surface."""

from __future__ import annotations

import pytest

import pmstate
from pmstate import (
    Event,
    EventTooLargeError,
    Log,
    Node,
    NodePathError,
    ReaderError,
    Table,
    Tree,
    append_event,
    compute_view,
    compute_view_at,
    load_agents_md,
    read_events,
)


def test_version_attribute() -> None:
    assert pmstate.__version__ == "0.1.1"


def test_phase_1_re_exports() -> None:
    assert Node is pmstate.Node
    assert Log is pmstate.Log
    assert Table is pmstate.Table
    assert NodePathError is pmstate.NodePathError


def test_phase_2_re_exports() -> None:
    assert Event is pmstate.Event
    assert append_event is pmstate.append_event
    assert read_events is pmstate.read_events
    assert EventTooLargeError is pmstate.EventTooLargeError
    assert ReaderError is pmstate.ReaderError


def test_phase_4_re_exports() -> None:
    assert Tree is pmstate.Tree
    assert compute_view is pmstate.compute_view
    assert compute_view_at is pmstate.compute_view_at
    assert load_agents_md is pmstate.load_agents_md


def test_phase_5_re_exports() -> None:
    assert pmstate.list_tree is not None
    assert pmstate.get_state is not None
    assert pmstate.find_state is not None
    assert pmstate.read_log is not None
    assert pmstate.ToolError is not None


def test_phase_6_claude_harness_lazy_import() -> None:
    Harness = pmstate.ClaudeHarness
    assert Harness.__name__ == "Harness"


def test_unknown_attribute_raises() -> None:
    with pytest.raises(AttributeError, match="has no attribute"):
        _ = pmstate.Definitely_Not_A_Real_Attribute  # type: ignore[attr-defined]


def test_all_list_matches_module_attrs() -> None:
    for name in pmstate.__all__:
        assert hasattr(pmstate, name), f"__all__ lists {name!r} but it's not on the module"
