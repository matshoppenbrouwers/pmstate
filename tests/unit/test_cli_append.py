"""Tests for ``pmstate append``."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from pmstate.cli import main


@pytest.fixture(autouse=True)
def _clean_user_modules() -> Iterator[None]:
    yield
    for cached in ("tree", "views", "reducers", "_pmstate_user_tree"):
        sys.modules.pop(cached, None)

_PROCUREMENT_YAML = """\
name: procurement
pmstate_version: "0.3.0"
tree:
  root: active
  nodes:
    - path: /active/procurement
      reducer: procurement_rollup
      children:
        - {name: quotes,  state: log, view: quote_view}
        - {name: lpos,    state: log, view: lpo_view}
        - {name: vendors, state: table}
events:
  quote.received:
    schema: {quote_id: str, vendor: str, amount: float}
  quote.approved:
    schema: {quote_id: str}
  lpo.issued:
    schema: {quote_id: str, lpo_number: str}
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    spec = tmp_path / "spec.yaml"
    spec.write_text(_PROCUREMENT_YAML)
    target = tmp_path / "proj"
    main(["init", "--from-spec", str(spec), str(target)])
    return target


def _read_log(project: Path, leaf: str) -> list[dict[str, object]]:
    log = project / "state" / f"{leaf}.jsonl"
    if not log.is_file():
        return []
    with log.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def test_append_happy_path(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/procurement/quotes",
        "--type", "quote.received",
        "--data", json.dumps({"quote_id": "Q1", "vendor": "acme", "amount": 100.0}),
    ])
    assert rc == 0
    rows = _read_log(project, "quotes")
    assert len(rows) == 1
    assert rows[0]["type"] == "pmstate.quote.received"
    assert rows[0]["source"] == "/procurement/quotes"
    assert rows[0]["data"] == {"quote_id": "Q1", "vendor": "acme", "amount": 100.0}


def test_append_data_from_stdin(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project)
    payload = json.dumps({"quote_id": "Q2", "vendor": "beta", "amount": 50.0})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    rc = main([
        "append", "/procurement/quotes", "--type", "quote.received", "--data", "-",
    ])
    assert rc == 0
    rows = _read_log(project, "quotes")
    assert rows[0]["data"]["vendor"] == "beta"


def test_append_propagates_overrides(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/procurement/quotes",
        "--type", "quote.received",
        "--data", json.dumps({"quote_id": "Q3", "vendor": "x", "amount": 1.0}),
        "--causationid", "parent-evt-1",
        "--subject", "quote-3",
    ])
    assert rc == 0
    rows = _read_log(project, "quotes")
    assert rows[0]["causationid"] == "parent-evt-1"
    assert rows[0]["subject"] == "quote-3"


def test_append_unknown_type_with_suggestion(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/procurement/quotes",
        "--type", "quote.recieved",  # typo
        "--data", json.dumps({"quote_id": "Q1", "vendor": "x", "amount": 1.0}),
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "did you mean" in err
    assert "quote.received" in err


def test_append_unknown_path(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/nonexistent",
        "--type", "quote.received",
        "--data", "{}",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "/nonexistent" in err


def test_append_non_log_leaf(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/procurement/vendors",
        "--type", "quote.received",
        "--data", json.dumps({"quote_id": "Q1", "vendor": "x", "amount": 1.0}),
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "state=log" in err.lower() or "state=table" in err.lower()


def test_append_no_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main([
        "append", "/x", "--type", "y.z",
        "--data", "{}",
    ])
    assert rc == 1
    assert "not in a pmstate project" in capsys.readouterr().err


def test_append_json_failure_is_parseable(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/procurement/quotes",
        "--type", "wrong.type", "--data", "{}", "--json",
    ])
    assert rc == 1
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert all("file" in i and "msg" in i for i in parsed)


def test_append_json_success_shape(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/procurement/quotes",
        "--type", "quote.received",
        "--data", json.dumps({"quote_id": "Q1", "vendor": "x", "amount": 1.0}),
        "--json",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed["id"], str)
    assert isinstance(parsed["path"], str)
    assert isinstance(parsed["bytes"], int)
    assert parsed["bytes"] > 0


def test_append_invalid_json_data(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/procurement/quotes",
        "--type", "quote.received", "--data", "{not-json",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "not valid JSON" in err


def test_append_data_must_be_object(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    rc = main([
        "append", "/procurement/quotes",
        "--type", "quote.received", "--data", "[1,2,3]",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "JSON object" in err
