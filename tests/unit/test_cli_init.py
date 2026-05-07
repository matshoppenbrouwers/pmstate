"""Tests for the ``pmstate init`` verb."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from pmstate.cli import main
from pmstate.tree import Tree

_HIRING_YAML = """\
name: hiring-pipeline
pmstate_version: "0.2.0"
tree:
  root: active
  nodes:
    - path: /active/pipeline
      reducer: pipeline_rollup
      children:
        - {name: leads,      state: log,   view: bucket_view}
        - {name: screened,   state: log,   view: bucket_view}
        - {name: interviews, state: log,   view: bucket_view}
        - {name: offers,     state: log,   view: bucket_view}
        - {name: hires,      state: log,   view: bucket_view}
        - {name: rejected,   state: table}
events:
  candidate.added:
    schema: {name: str, source: str}
"""


def _load_build_tree(project: Path) -> object:
    spec = importlib.util.spec_from_file_location(
        f"_test_tree_{project.name}", project / "tree.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(project))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(project))
    return module.build_tree  # type: ignore[attr-defined]


def test_default_writes_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(["init"])
    assert rc == 0
    assert (tmp_path / "pmstate.example.yaml").is_file()


def test_default_refuses_when_example_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pmstate.example.yaml").write_text("hi\n")
    rc = main(["init"])
    assert rc == 1
    assert "already exists" in capsys.readouterr().err


def test_from_spec_generates_files(tmp_path: Path) -> None:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(_HIRING_YAML)
    project = tmp_path / "proj"
    rc = main(["init", "--from-spec", str(spec_file), str(project)])
    assert rc == 0
    for fname in ("tree.py", "views.py", "reducers.py", "chat.py", "AGENTS.md", "pmstate.yaml"):
        assert (project / fname).is_file(), fname
    assert (project / "state" / ".gitignore").is_file()
    assert (project / "state" / ".gitignore").read_text().startswith("*\n")


def test_from_spec_round_trip(tmp_path: Path) -> None:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(_HIRING_YAML)
    project = tmp_path / "proj"
    rc = main(["init", "--from-spec", str(spec_file), str(project)])
    assert rc == 0
    build_tree = _load_build_tree(project)
    tree = build_tree()
    assert isinstance(tree, Tree)
    assert tree.name == "hiring-pipeline"
    assert tree.root.name == "active"
    pipeline = tree.root.children[0]
    assert pipeline.name == "pipeline"
    assert pipeline.reducer is not None
    child_names = [c.name for c in pipeline.children]
    assert child_names == ["leads", "screened", "interviews", "offers", "hires", "rejected"]


def test_from_spec_refuses_collision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(_HIRING_YAML)
    project = tmp_path / "proj"
    project.mkdir()
    (project / "tree.py").write_text("# user code\n")
    rc = main(["init", "--from-spec", str(spec_file), str(project)])
    assert rc == 1
    assert "refusing to overwrite" in capsys.readouterr().err
    assert (project / "tree.py").read_text() == "# user code\n"


def test_from_spec_force_overwrites(tmp_path: Path) -> None:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(_HIRING_YAML)
    project = tmp_path / "proj"
    project.mkdir()
    (project / "tree.py").write_text("# user code\n")
    rc = main(["init", "--from-spec", str(spec_file), str(project), "--force"])
    assert rc == 0
    assert "user code" not in (project / "tree.py").read_text()


def test_upgrade_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(_HIRING_YAML)
    project = tmp_path / "proj"
    main(["init", "--from-spec", str(spec_file), str(project)])
    snapshot = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    monkeypatch.chdir(project)
    rc = main(["init", "--upgrade"])
    assert rc == 0
    after = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert snapshot == after, "upgrade was not byte-stable on unchanged spec"


def test_upgrade_appends_new_view_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(_HIRING_YAML)
    project = tmp_path / "proj"
    main(["init", "--from-spec", str(spec_file), str(project)])
    custom_views = project / "views.py"
    custom_views.write_text(
        "# my edits\nfrom collections.abc import Iterable\nfrom typing import Any\n\n"
        "def bucket_view(events): return {}\n"
    )
    new_spec = _HIRING_YAML.replace(
        "- {name: rejected,   state: table}",
        "- {name: rejected,   state: table}\n        - {name: parked, state: log, view: parked_view}",
    )
    (project / "pmstate.yaml").write_text(new_spec)
    monkeypatch.chdir(project)
    rc = main(["init", "--upgrade"])
    assert rc == 0
    text = custom_views.read_text()
    assert "# my edits" in text
    assert "bucket_view" in text
    assert "parked_view" in text


def test_upgrade_outside_project_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(["init", "--upgrade"])
    assert rc == 1
    assert "not in a pmstate project" in capsys.readouterr().err


def test_unknown_state_aborts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(
        "name: x\npmstate_version: '0.2.0'\ntree:\n  root: r\n  nodes:\n"
        "    - path: /r/x\n      children:\n        - {name: bad, state: bogus}\n"
    )
    rc = main(["init", "--from-spec", str(spec_file), str(tmp_path / "proj")])
    assert rc == 1
    assert "could not parse spec" in capsys.readouterr().err
