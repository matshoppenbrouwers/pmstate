"""Per-source view for the generic feedback example.

Folds a single source's event log into lifecycle counts. Each feedback item
moves ``captured`` (open) → ``triaged`` → ``resolved``; later states override
earlier ones regardless of arrival order (``resolved`` wins over ``triaged``
wins over ``captured``).
"""
from collections.abc import Iterable
from typing import Any


def source_view(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold one source's events into ``{open, triaged, resolved, by_severity}``."""
    captured: dict[str, dict[str, Any]] = {}
    state: dict[str, str] = {}
    for e in events:
        etype = e["type"]
        fid = e["data"]["feedback_id"]
        if etype.startswith("pmstate.feedback.captured"):
            captured[fid] = e["data"]
            state.setdefault(fid, "open")
        elif etype.startswith("pmstate.feedback.triaged"):
            if state.get(fid) != "resolved":
                state[fid] = "triaged"
        elif etype.startswith("pmstate.feedback.resolved"):
            state[fid] = "resolved"

    open_ids = [fid for fid, s in state.items() if s == "open"]
    by_severity: dict[str, int] = {}
    for fid in open_ids:
        severity = captured.get(fid, {}).get("severity", "unknown")
        by_severity[severity] = by_severity.get(severity, 0) + 1

    return {
        "open": len(open_ids),
        "triaged": sum(1 for s in state.values() if s == "triaged"),
        "resolved": sum(1 for s in state.values() if s == "resolved"),
        "by_severity": by_severity,
    }
