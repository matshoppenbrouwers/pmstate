"""CI parity check: every key in `_spec.py` must appear in spec-authoring.md.

Catches schema additions that ship without docs.
"""

from __future__ import annotations

from pathlib import Path

import attrs

from pmstate.cli._spec import EventSchema, NodeSpec, Spec, TreeSpec

_DOC = Path(__file__).resolve().parents[2] / "docs" / "spec-authoring.md"


def _field_names(cls: type) -> set[str]:
    return {f.name for f in attrs.fields(cls)}


def test_spec_keys_documented() -> None:
    text = _DOC.read_text(encoding="utf-8")
    expected = _field_names(Spec) | _field_names(TreeSpec) | _field_names(NodeSpec) | {"schema"}
    expected -= {"fields"}  # internal name; surfaces as "schema" in user-facing docs
    missing = sorted(name for name in expected if name not in text)
    assert not missing, (
        f"docs/spec-authoring.md is missing keys from _spec.py: {missing}\n"
        "Add them to the schema reference section."
    )


def test_event_schema_documented() -> None:
    """The 'fields' attr surfaces as the literal 'schema:' YAML key."""
    text = _DOC.read_text(encoding="utf-8")
    assert "schema:" in text
    assert _field_names(EventSchema) == {"fields"}
