"""Tests for pmstate._paths."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pmstate._paths import NodePathError, format, parse


def test_parse_root() -> None:
    assert parse("/") == ()
    assert parse("") == ()


def test_parse_single_segment() -> None:
    assert parse("/active") == ("active",)


def test_parse_multi_segment() -> None:
    assert parse("/active/procurement/quotes") == ("active", "procurement", "quotes")


def test_parse_no_leading_slash() -> None:
    with pytest.raises(NodePathError, match="must start with"):
        parse("a/b")


def test_parse_double_slash() -> None:
    with pytest.raises(NodePathError, match="empty segment"):
        parse("/a//b")


def test_parse_trailing_slash() -> None:
    with pytest.raises(NodePathError, match="empty segment"):
        parse("/a/")


def test_parse_whitespace_segment() -> None:
    with pytest.raises(NodePathError, match="whitespace"):
        parse("/a/ b")


def test_parse_non_string() -> None:
    with pytest.raises(NodePathError, match="must be a string"):
        parse(123)  # type: ignore[arg-type]


def test_format_root() -> None:
    assert format(()) == "/"


def test_format_multi() -> None:
    assert format(("a", "b", "c")) == "/a/b/c"


def test_node_path_error_carries_path() -> None:
    try:
        parse("bad")
    except NodePathError as e:
        assert e.path == "bad"
        assert "must start with" in str(e)


_segment = st.text(alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E,
                                          blacklist_characters="/"),
                   min_size=1, max_size=8).filter(lambda s: s == s.strip())


@given(st.lists(_segment, min_size=0, max_size=6).map(tuple))
def test_round_trip_format_parse(parts: tuple[str, ...]) -> None:
    assert parse(format(parts)) == parts
