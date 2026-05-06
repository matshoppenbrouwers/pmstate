"""Tests for the pmstate public API surface."""

from __future__ import annotations

import pmstate
from pmstate import Log, Node, NodePathError, Table


def test_version_attribute() -> None:
    assert pmstate.__version__ == "0.0.1"


def test_phase_1_re_exports() -> None:
    assert Node is pmstate.Node
    assert Log is pmstate.Log
    assert Table is pmstate.Table
    assert NodePathError is pmstate.NodePathError


def test_all_list_matches_module_attrs() -> None:
    for name in pmstate.__all__:
        assert hasattr(pmstate, name), f"__all__ lists {name!r} but it's not on the module"
