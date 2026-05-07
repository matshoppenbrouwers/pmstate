"""Tests for ``pmstate validate``."""

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
        - {name: leads, state: log, view: bucket_view}
        - {name: rejected, state: table}
events:
  candidate.added:
    schema: {name: str}
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(_HIRING_YAML)
    target = tmp_path / "proj"
    main(["init", "--from-spec", str(spec_file), str(target)])
    return target


def test_happy_path(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(project)
    rc = main(["validate"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK" in out


def test_no_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(["validate"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not in a pmstate project" in err


def test_broken_yaml(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "pmstate.yaml").write_text("name: x\nbad:\n  - {missing\n")
    monkeypatch.chdir(project)
    rc = main(["validate"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "error" in out


def test_unimportable_tree_py(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "tree.py").write_text("raise RuntimeError('boom')\n")
    monkeypatch.chdir(project)
    rc = main(["validate"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "RuntimeError" in out


def test_build_tree_returns_non_tree(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "tree.py").write_text("def build_tree():\n    return 'oops'\n")
    monkeypatch.chdir(project)
    rc = main(["validate"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "not Tree" in out


def test_views_unimportable(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "views.py").write_text("raise RuntimeError('views explosion')\n")
    monkeypatch.chdir(project)
    rc = main(["validate"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "views explosion" in out


def test_missing_agents_md_warns(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "AGENTS.md").unlink()
    monkeypatch.chdir(project)
    rc = main(["validate"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "warn" in out
    assert "AGENTS.md" in out


def test_empty_agents_md_errors(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "AGENTS.md").write_text("")
    monkeypatch.chdir(project)
    rc = main(["validate"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "AGENTS.md is empty" in out


def test_json_output_parseable(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(project)
    rc = main(["validate", "--json"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert rc == 0


def test_json_includes_errors(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "AGENTS.md").write_text("")
    monkeypatch.chdir(project)
    rc = main(["validate", "--json"])
    parsed = json.loads(capsys.readouterr().out)
    assert rc == 1
    levels = {item["level"] for item in parsed}
    assert "error" in levels


def test_strict_skips_when_tools_absent(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import pmstate.cli.validate as mod

    monkeypatch.setattr(mod.shutil, "which", lambda _name: None)
    monkeypatch.chdir(project)
    rc = main(["validate", "--strict"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "skipped" in out
