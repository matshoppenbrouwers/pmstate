"""Hypothesis property tests for the envelope/writer/reader round-trip."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from pmstate.envelope import Event
from pmstate.reader import read_events
from pmstate.writer import append_event

_safe_strs = st.text(
    alphabet=st.characters(
        min_codepoint=0x20,
        max_codepoint=0x7E,
        blacklist_characters='"\\',
    ),
    min_size=0,
    max_size=20,
)
_data_dicts = st.dictionaries(
    keys=st.text(min_size=1, max_size=8, alphabet="abcdefghij_"),
    values=st.one_of(st.integers(), _safe_strs, st.booleans(), st.none()),
    max_size=5,
)


def _event_strategy() -> st.SearchStrategy[Event]:
    return st.builds(
        lambda data, subject: Event.new(
            type="pmstate.test.event",
            source="/active/test",
            data=data,
            subject=subject if subject else None,
        ),
        data=st.one_of(st.none(), _data_dicts),
        subject=_safe_strs,
    )


@given(_event_strategy())
def test_to_dict_from_dict_round_trip(event: Event) -> None:
    assert Event.from_dict(event.to_dict()) == event


@given(st.lists(_event_strategy(), min_size=0, max_size=20))
@settings(max_examples=50, deadline=None)
def test_write_then_read_round_trip(events: list[Event]) -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "log.jsonl"
        for e in events:
            append_event(p, e)
        if not events:
            assert not p.exists() or list(read_events(p)) == []
            return
        rows = list(read_events(p))
        assert rows == [e.to_dict() for e in events]


@given(
    st.integers(min_value=0, max_value=50),
    st.integers(min_value=0, max_value=50),
)
@settings(max_examples=30, deadline=None)
def test_limit_caps_yield_count(n: int, k: int) -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "log.jsonl"
        for i in range(n):
            append_event(
                p,
                Event.new(type="pmstate.test.event", source="/x", data={"i": i}),
            )
        rows = list(read_events(p, limit=k)) if n > 0 else []
        assert len(rows) == min(n, k)


def test_5000_ulids_unique_via_event_new() -> None:
    ids = {Event.new(type="pmstate.test.event", source="/x").id for _ in range(5000)}
    assert len(ids) == 5000
