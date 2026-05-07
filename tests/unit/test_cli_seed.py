"""Tests for ``pmstate seed``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pmstate.cli import main

_HIRING_YAML = """\
name: hiring
pmstate_version: "0.2.0"
tree:
  root: active
  nodes:
    - path: /active/pipeline
      reducer: pipeline_rollup
      children:
        - {name: leads,      state: log, view: bucket_view}
        - {name: screened,   state: log, view: bucket_view}
        - {name: interviews, state: log, view: bucket_view}
        - {name: offers,     state: log, view: bucket_view}
        - {name: hires,      state: log, view: bucket_view}
events:
  candidate.added:
    schema: {name: str, source: str}
  candidate.advanced:
    schema: {from: str, to: str, note: str}
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    spec = tmp_path / "spec.yaml"
    spec.write_text(_HIRING_YAML)
    target = tmp_path / "proj"
    main(["init", "--from-spec", str(spec), str(target)])
    return target


def _count_events(project: Path) -> int:
    total = 0
    for log in (project / "state").glob("*.jsonl"):
        with log.open() as f:
            total += sum(1 for line in f if line.strip())
    return total


def test_seed_distributes_30(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project)
    rc = main(["seed", "--n", "30", "--seed", "42"])
    assert rc == 0
    assert _count_events(project) == 30
    log_files = sorted((project / "state").glob("*.jsonl"))
    assert len(log_files) == 5  # one per Log leaf


def test_seed_is_deterministic(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project)
    main(["seed", "--n", "30", "--seed", "42"])
    snapshot = {p.name: p.read_bytes() for p in (project / "state").glob("*.jsonl")}
    main(["seed", "--n", "30", "--seed", "42", "--force"])
    after = {p.name: p.read_bytes() for p in (project / "state").glob("*.jsonl")}
    assert snapshot == after


def test_seed_refuses_when_state_non_empty(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    main(["seed", "--n", "5", "--seed", "1"])
    rc = main(["seed", "--n", "5", "--seed", "1"])
    assert rc == 1
    assert "--force" in capsys.readouterr().err


def test_seed_force_overrides(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project)
    main(["seed", "--n", "5", "--seed", "1"])
    rc = main(["seed", "--n", "10", "--seed", "1", "--force"])
    assert rc == 0
    assert _count_events(project) == 10


def test_seed_no_log_leaves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    spec_yaml = """\
name: t
pmstate_version: "0.2.0"
tree:
  root: r
  nodes:
    - path: /r/x
      children:
        - {name: only_table, state: table}
"""
    spec = tmp_path / "spec.yaml"
    spec.write_text(spec_yaml)
    target = tmp_path / "proj"
    main(["init", "--from-spec", str(spec), str(target)])
    monkeypatch.chdir(target)
    rc = main(["seed", "--n", "5"])
    assert rc == 0
    assert "no Log leaves" in capsys.readouterr().out


def test_seed_no_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(["seed"])
    assert rc == 1
    assert "not in a pmstate project" in capsys.readouterr().err


def test_seed_payloads_match_schema(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project)
    main(["seed", "--n", "10", "--seed", "7"])
    log = project / "state" / "leads.jsonl"
    assert log.is_file()
    with log.open() as f:
        for line in f:
            evt = json.loads(line)
            assert evt["type"].startswith("pmstate.")
            assert isinstance(evt["data"], dict)
            for v in evt["data"].values():
                assert isinstance(v, str)
