"""Per-leaf views for the procurement example."""
from collections.abc import Iterable
from typing import Any


def quote_view(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Vendor quotes received and pending approval."""
    rows = list(events)
    is_recv = lambda e: e["type"].startswith("pmstate.quote.received")  # noqa: E731
    is_appr = lambda e: e["type"].startswith("pmstate.quote.approved")  # noqa: E731
    approved = {e["data"]["quote_id"] for e in rows if is_appr(e)}
    pending = [e for e in rows if is_recv(e) and e["id"] not in approved]
    return {"pending_count": len(pending), "latest": pending[-1] if pending else None}


def lpo_view(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """LPOs issued."""
    rows = [e for e in events if e["type"].startswith("pmstate.lpo.issued")]
    return {"count": len(rows), "latest": rows[-1] if rows else None}
