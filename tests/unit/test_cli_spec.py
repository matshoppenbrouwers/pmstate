"""Tests for ``pmstate.yaml`` parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from pmstate.cli._spec import (
    EventSchema,
    NodeSpec,
    Spec,
    SpecError,
    TreeSpec,
    parse_spec,
)

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
  candidate.advanced:
    schema: {from: str, to: str, note: str}
"""


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "pmstate.yaml"
    p.write_text(body)
    return p


def test_happy_path(tmp_path: Path) -> None:
    spec = parse_spec(_write(tmp_path, _HIRING_YAML))
    assert isinstance(spec, Spec)
    assert spec.name == "hiring-pipeline"
    assert spec.pmstate_version == "0.2.0"
    assert spec.root == "active"
    assert len(spec.nodes) == 1
    tree0 = spec.nodes[0]
    assert isinstance(tree0, TreeSpec)
    assert tree0.path == "/active/pipeline"
    assert tree0.reducer == "pipeline_rollup"
    assert len(tree0.children) == 6
    leads = tree0.children[0]
    assert isinstance(leads, NodeSpec)
    assert leads.name == "leads"
    assert leads.state == "log"
    assert leads.view == "bucket_view"
    rejected = tree0.children[-1]
    assert rejected.state == "table"
    assert rejected.view is None
    assert "candidate.added" in spec.events
    assert isinstance(spec.events["candidate.added"], EventSchema)
    assert spec.events["candidate.added"].fields == {"name": "str", "source": "str"}


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SpecError) as excinfo:
        parse_spec(tmp_path / "nope.yaml")
    assert "not found" in excinfo.value.msg


def test_empty_file(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="empty"):
        parse_spec(_write(tmp_path, ""))


def test_invalid_yaml(tmp_path: Path) -> None:
    with pytest.raises(SpecError) as excinfo:
        parse_spec(_write(tmp_path, "name: foo\n  bad:\n  worse"))
    assert "invalid YAML" in excinfo.value.msg


def test_missing_name(tmp_path: Path) -> None:
    body = "pmstate_version: '0.2.0'\ntree:\n  root: r\n  nodes: []\n"
    with pytest.raises(SpecError, match="'name'"):
        parse_spec(_write(tmp_path, body))


def test_missing_pmstate_version(tmp_path: Path) -> None:
    body = "name: x\ntree:\n  root: r\n  nodes: []\n"
    with pytest.raises(SpecError, match="'pmstate_version'"):
        parse_spec(_write(tmp_path, body))


def test_missing_tree(tmp_path: Path) -> None:
    body = "name: x\npmstate_version: '0.2.0'\n"
    with pytest.raises(SpecError, match="'tree'"):
        parse_spec(_write(tmp_path, body))


def test_invalid_state(tmp_path: Path) -> None:
    body = """\
name: x
pmstate_version: '0.2.0'
tree:
  root: r
  nodes:
    - path: /a
      children:
        - {name: bad, state: explosion}
"""
    with pytest.raises(SpecError, match="must be one of"):
        parse_spec(_write(tmp_path, body))


def test_path_must_start_with_slash(tmp_path: Path) -> None:
    body = """\
name: x
pmstate_version: '0.2.0'
tree:
  root: r
  nodes:
    - path: bad
      children: []
"""
    with pytest.raises(SpecError, match="must start with '/'"):
        parse_spec(_write(tmp_path, body))


def test_unknown_node_key(tmp_path: Path) -> None:
    body = """\
name: x
pmstate_version: '0.2.0'
tree:
  root: r
  nodes:
    - path: /a
      children:
        - {name: x, state: log, weird: 1}
"""
    with pytest.raises(SpecError, match="unknown child key"):
        parse_spec(_write(tmp_path, body))


def test_unknown_tree_key(tmp_path: Path) -> None:
    body = """\
name: x
pmstate_version: '0.2.0'
tree:
  root: r
  nodes:
    - path: /a
      weird: 1
      children: []
"""
    with pytest.raises(SpecError, match="unknown tree node key"):
        parse_spec(_write(tmp_path, body))


def test_events_must_be_mapping(tmp_path: Path) -> None:
    body = """\
name: x
pmstate_version: '0.2.0'
tree:
  root: r
  nodes:
    - path: /a
      children: []
events: not-a-map
"""
    with pytest.raises(SpecError, match="'events' must be a mapping"):
        parse_spec(_write(tmp_path, body))


def test_event_schema_must_be_mapping(tmp_path: Path) -> None:
    body = """\
name: x
pmstate_version: '0.2.0'
tree:
  root: r
  nodes:
    - path: /a
      children: []
events:
  bad.event:
    schema: oops
"""
    with pytest.raises(SpecError, match="schema must be a mapping"):
        parse_spec(_write(tmp_path, body))


def test_unicode_names(tmp_path: Path) -> None:
    body = """\
name: süß
pmstate_version: '0.2.0'
tree:
  root: 模型
  nodes:
    - path: /模型
      children:
        - {name: 子, state: log}
"""
    spec = parse_spec(_write(tmp_path, body))
    assert spec.name == "süß"
    assert spec.root == "模型"
    assert spec.nodes[0].children[0].name == "子"


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="must be a mapping"):
        parse_spec(_write(tmp_path, "- foo\n- bar\n"))


def test_children_must_be_list(tmp_path: Path) -> None:
    body = """\
name: x
pmstate_version: '0.2.0'
tree:
  root: r
  nodes:
    - path: /a
      children: not-a-list
"""
    with pytest.raises(SpecError, match="'children' must be a list"):
        parse_spec(_write(tmp_path, body))
