"""Tests for pmstate.upcasters."""

from __future__ import annotations

from typing import Any

import pytest

from pmstate.upcasters import UpcastCycleError, UpcasterRegistry, default_registry
from pmstate.upcasters import default_registry as default_registry_alias


def test_no_op_when_type_not_registered() -> None:
    reg = UpcasterRegistry()
    event = {"type": "pmstate.q.r", "data": {"x": 1}}
    assert reg.upcast(event) is event


def test_single_step_transform() -> None:
    reg = UpcasterRegistry()

    def to_v2(d: dict[str, Any]) -> dict[str, Any]:
        return {**d, "type": "pmstate.q.r.v2", "data": {**d.get("data", {}), "added": True}}

    reg.register("pmstate.q.r", to_v2)
    out = reg.upcast({"type": "pmstate.q.r", "data": {"x": 1}})
    assert out["type"] == "pmstate.q.r.v2"
    assert out["data"] == {"x": 1, "added": True}


def test_chain_three_hops() -> None:
    reg = UpcasterRegistry()
    reg.register("pmstate.q.r", lambda d: {**d, "type": "pmstate.q.r.v2"})
    reg.register("pmstate.q.r.v2", lambda d: {**d, "type": "pmstate.q.r.v3"})
    reg.register("pmstate.q.r.v3", lambda d: {**d, "type": "pmstate.q.r.v4"})
    out = reg.upcast({"type": "pmstate.q.r"})
    assert out["type"] == "pmstate.q.r.v4"


def test_cycle_detection() -> None:
    reg = UpcasterRegistry()
    reg.register("pmstate.a.x", lambda d: {**d, "type": "pmstate.b.y"})
    reg.register("pmstate.b.y", lambda d: {**d, "type": "pmstate.a.x"})
    with pytest.raises(UpcastCycleError) as exc:
        reg.upcast({"type": "pmstate.a.x"})
    assert "pmstate.a.x" in exc.value.chain


def test_duplicate_registration_rejected() -> None:
    reg = UpcasterRegistry()
    reg.register("pmstate.q.r", lambda d: d)
    with pytest.raises(ValueError, match="already registered"):
        reg.register("pmstate.q.r", lambda d: d)


def test_default_registry_is_singleton() -> None:
    assert default_registry is default_registry_alias


def test_missing_type_key_is_no_op() -> None:
    reg = UpcasterRegistry()
    out = reg.upcast({"no_type_key": 1})
    assert out == {"no_type_key": 1}
