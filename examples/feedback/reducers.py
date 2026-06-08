"""Feedback-level rollup reducer.

Aggregates per-source views (``/web``, ``/chat``) into one health view across
all feedback sources.
"""
from typing import Any


def feedback_rollup(children: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Roll child source views up into open/triaged/resolved + severity/source breakdowns."""
    by_severity: dict[str, int] = {}
    for child in children.values():
        for severity, count in child.get("by_severity", {}).items():
            by_severity[severity] = by_severity.get(severity, 0) + count

    return {
        "open": sum(c.get("open", 0) for c in children.values()),
        "triaged": sum(c.get("triaged", 0) for c in children.values()),
        "resolved": sum(c.get("resolved", 0) for c in children.values()),
        "by_severity": by_severity,
        "by_source": {name: c.get("open", 0) for name, c in children.items()},
    }
