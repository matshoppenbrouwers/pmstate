"""Tests for pmstate.envelope."""

from __future__ import annotations

import re

import pytest

from pmstate.envelope import Event


def test_new_populates_id_and_time() -> None:
    e = Event.new(type="pmstate.quote.received", source="/active/procurement/quotes")
    assert len(e.id) == 26
    assert e.specversion == "1.0"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", e.time)


def test_new_with_data() -> None:
    e = Event.new(
        type="pmstate.quote.received",
        source="/active/procurement/quotes",
        data={"vendor": "Acme"},
    )
    assert e.data == {"vendor": "Acme"}


def test_to_dict_drops_none_optionals() -> None:
    e = Event.new(type="pmstate.quote.received", source="/active/procurement/quotes")
    d = e.to_dict()
    assert "subject" not in d
    assert "data" not in d
    assert "causationid" not in d
    assert d["specversion"] == "1.0"


def test_to_dict_includes_set_optionals() -> None:
    e = Event.new(
        type="pmstate.quote.received",
        source="/active/procurement/quotes",
        data={"x": 1},
        subject="vendor-acme",
        causationid="01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )
    d = e.to_dict()
    assert d["subject"] == "vendor-acme"
    assert d["data"] == {"x": 1}
    assert d["causationid"] == "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_round_trip() -> None:
    e1 = Event.new(
        type="pmstate.quote.received",
        source="/active/procurement/quotes",
        data={"vendor": "X"},
        subject="vendor-x",
    )
    e2 = Event.from_dict(e1.to_dict())
    assert e2 == e1


def test_type_regex_accepts_valid() -> None:
    Event.new(type="pmstate.quote.received", source="/")
    Event.new(type="pmstate.quote.approved.v2", source="/")
    Event.new(type="pmstate.foo_bar.baz_qux", source="/")


def test_type_regex_rejects_uppercase() -> None:
    with pytest.raises(ValueError, match="must match"):
        Event.new(type="pmstate.Quote.Received", source="/")


def test_type_regex_rejects_no_dotted_namespace() -> None:
    with pytest.raises(ValueError, match="must match"):
        Event.new(type="pmstate.quote", source="/")


def test_type_regex_rejects_wrong_prefix() -> None:
    with pytest.raises(ValueError, match="must match"):
        Event.new(type="other.quote.received", source="/")


def test_source_must_start_with_slash() -> None:
    with pytest.raises(ValueError, match="start with"):
        Event.new(type="pmstate.quote.received", source="active/procurement")


def test_specversion_default_is_one() -> None:
    e = Event.new(type="pmstate.quote.received", source="/")
    assert e.specversion == "1.0"


def test_from_dict_handles_missing_specversion() -> None:
    d = {
        "id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "source": "/x",
        "type": "pmstate.quote.received",
        "time": "2026-05-06T10:00:00.000Z",
    }
    e = Event.from_dict(d)
    assert e.specversion == "1.0"
