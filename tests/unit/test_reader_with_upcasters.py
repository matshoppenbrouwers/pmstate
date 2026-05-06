"""Integration: reader applies upcasters from the explicit and default registries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import pmstate
from pmstate.envelope import Event
from pmstate.reader import read_events
from pmstate.upcasters import UpcasterRegistry, default_registry
from pmstate.writer import append_event


def _seed_v1(p: Path, n: int) -> None:
    for i in range(n):
        append_event(
            p,
            Event.new(
                type="pmstate.quote.received",
                source="/active/procurement/quotes",
                data={"i": i},
            ),
        )


def test_explicit_registry_upcasts_v1_to_v2(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed_v1(p, 3)

    reg = UpcasterRegistry()

    def to_v2(d: dict[str, Any]) -> dict[str, Any]:
        return {**d, "type": "pmstate.quote.received.v2", "data": {**d["data"], "added": True}}

    reg.register("pmstate.quote.received", to_v2)

    rows = list(read_events(p, registry=reg))
    assert len(rows) == 3
    assert all(r["type"] == "pmstate.quote.received.v2" for r in rows)
    assert all(r["data"]["added"] is True for r in rows)


def test_default_registry_used_when_none(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    _seed_v1(p, 2)

    rows = list(read_events(p))
    assert all(r["type"] == "pmstate.quote.received" for r in rows)


def test_default_registry_picks_up_global_registration(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    append_event(
        p,
        Event.new(
            type="pmstate.global.registered",
            source="/x",
            data={"k": "v"},
        ),
    )

    def adder(d: dict[str, Any]) -> dict[str, Any]:
        return {**d, "type": "pmstate.global.registered.v2", "data": {**d["data"], "added": 1}}

    default_registry.register("pmstate.global.registered", adder)
    try:
        rows = list(read_events(p))
        assert rows[0]["type"] == "pmstate.global.registered.v2"
        assert rows[0]["data"]["added"] == 1
    finally:
        default_registry._upcasters.pop("pmstate.global.registered", None)


def test_phase_3_re_exports() -> None:
    assert pmstate.UpcasterRegistry is UpcasterRegistry
    assert pmstate.default_registry is default_registry
    assert hasattr(pmstate, "Upcaster")
    assert hasattr(pmstate, "UpcastCycleError")


@pytest.fixture(autouse=True)
def _reset_default_registry() -> Any:
    snapshot = dict(default_registry._upcasters)
    yield
    default_registry._upcasters.clear()
    default_registry._upcasters.update(snapshot)
