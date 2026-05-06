"""Procurement-level rollup reducer."""
from typing import Any


def procurement_rollup(children: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Open quotes, open LPOs, blocked when > 5 pending."""
    pending = children["quotes"].get("pending_count", 0)
    return {
        "open_quotes": pending,
        "open_lpos": children["lpos"].get("count", 0),
        "blocked": pending > 5,  # noqa: PLR2004 — domain threshold, intentional inline
    }
