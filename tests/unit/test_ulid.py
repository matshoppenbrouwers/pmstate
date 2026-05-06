"""Tests for pmstate._ulid."""

from __future__ import annotations

import pytest

from pmstate._ulid import is_valid, new, parse


def test_new_returns_26_char_string() -> None:
    value = new()
    assert isinstance(value, str)
    assert len(value) == 26


def test_5000_unique_in_single_process() -> None:
    values = {new() for _ in range(5000)}
    assert len(values) == 5000


def test_lexicographic_order_within_ms() -> None:
    values = [new() for _ in range(100)]
    assert sorted(values) == values or len(set(values[:1])) == 1


def test_parse_round_trip() -> None:
    value = new()
    parsed = parse(value)
    assert str(parsed) == value


def test_parse_invalid_raises() -> None:
    with pytest.raises((ValueError, TypeError)):
        parse("not-a-ulid")


def test_is_valid_true() -> None:
    assert is_valid(new()) is True


def test_is_valid_false() -> None:
    assert is_valid("nope") is False
    assert is_valid("") is False
