"""Tests for pmstate.storage."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import attrs.exceptions
import pytest

from pmstate.storage import Log, Table


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


# ---- Log ----


def test_log_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    assert Log(p).read() == {"count": 0, "first": None, "latest": None}


def test_log_single_row(tmp_path: Path) -> None:
    p = tmp_path / "one.jsonl"
    _write_jsonl(p, [{"id": "a"}])
    assert Log(p).read() == {"count": 1, "first": {"id": "a"}, "latest": {"id": "a"}}


def test_log_many_rows(tmp_path: Path) -> None:
    p = tmp_path / "many.jsonl"
    _write_jsonl(p, [{"i": i} for i in range(1000)])
    out = Log(p).read()
    assert out["count"] == 1000
    assert out["first"] == {"i": 0}
    assert out["latest"] == {"i": 999}


def test_log_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "blanks.jsonl"
    p.write_text('{"a":1}\n\n{"a":2}\n', encoding="utf-8")
    assert Log(p).read()["count"] == 2


def test_log_custom_view(tmp_path: Path) -> None:
    p = tmp_path / "c.jsonl"
    _write_jsonl(p, [{"x": 1}, {"x": 2}, {"x": 3}])

    def sum_view(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
        return {"sum": sum(int(e["x"]) for e in events)}

    assert Log(p, view=sum_view).read() == {"sum": 6}


def test_log_view_exception_becomes_error(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    _write_jsonl(p, [{"a": 1}])

    def bad_view(_events: Iterable[dict[str, Any]]) -> dict[str, Any]:
        raise ValueError("nope")

    out = Log(p, view=bad_view).read()
    assert out == {"error": "nope", "exception": "ValueError", "path": str(p)}


def test_log_missing_file_returns_error(tmp_path: Path) -> None:
    p = tmp_path / "missing.jsonl"
    out = Log(p).read()
    assert out["exception"] == "FileNotFoundError"
    assert out["path"] == str(p)


def test_log_path_accepts_str(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _write_jsonl(p, [{"a": 1}])
    assert Log(str(p)).read()["count"] == 1


def test_log_is_frozen(tmp_path: Path) -> None:
    p = tmp_path / "f.jsonl"
    p.write_text("", encoding="utf-8")
    log = Log(p)
    with pytest.raises(attrs.exceptions.FrozenInstanceError):
        log.path = tmp_path / "other"  # type: ignore[misc]


# ---- Table ----


def test_table_default_view_small_doc(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    p.write_text('{"name": "alice", "active": true}', encoding="utf-8")
    assert Table(p).read() == {"name": "alice", "active": True}


def test_table_truncates_by_size(tmp_path: Path) -> None:
    p = tmp_path / "big.json"
    p.write_text(json.dumps({"k": "x" * 5000}), encoding="utf-8")
    out = Table(p).read()
    assert out["_truncated"] is True
    assert out["size_bytes"] > 2048


def test_table_truncates_by_key_count(tmp_path: Path) -> None:
    p = tmp_path / "wide.json"
    p.write_text(json.dumps({f"k{i}": i for i in range(60)}), encoding="utf-8")
    out = Table(p).read()
    assert out["_truncated"] is True
    assert len(out["keys"]) == 50


def test_table_custom_view(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    p.write_text('{"a": 1, "b": 2}', encoding="utf-8")

    def view(doc: Any) -> dict[str, Any]:
        return {"sum": sum(doc.values())}

    assert Table(p, view=view).read() == {"sum": 3}


def test_table_view_exception_becomes_error(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    p.write_text('{"a": 1}', encoding="utf-8")

    def bad_view(_doc: Any) -> dict[str, Any]:
        raise RuntimeError("fail")

    out = Table(p, view=bad_view).read()
    assert out["exception"] == "RuntimeError"
    assert out["error"] == "fail"


def test_table_missing_file_returns_error(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    assert Table(p).read()["exception"] == "FileNotFoundError"


def test_table_non_dict_value(tmp_path: Path) -> None:
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert Table(p).read() == {"value": [1, 2, 3]}


def test_table_is_frozen(tmp_path: Path) -> None:
    p = tmp_path / "f.json"
    p.write_text("{}", encoding="utf-8")
    table = Table(p)
    with pytest.raises(attrs.exceptions.FrozenInstanceError):
        table.path = tmp_path / "other"  # type: ignore[misc]
