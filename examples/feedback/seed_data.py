"""Generate deterministic feedback events under examples/feedback/state/.

Run with::

    python -m examples.feedback.seed_data

Reproducible (seed=42), idempotent (deletes existing state files first).
Populates both the ``/web`` and ``/chat`` leaves with ``feedback.captured``
events across multiple sources and severities, then triages a subset.
"""

from __future__ import annotations

import random
from pathlib import Path

from pmstate import Event, append_event

STATE_DIR = Path(__file__).parent / "state"

_SEVERITIES = ["low", "medium", "high", "critical"]
_CATEGORIES = ["bug", "ux", "performance", "feature-request"]
_SUMMARIES = [
    "Export button does nothing",
    "Slow load on dashboard",
    "Typo in onboarding copy",
    "Cannot reset password",
    "Confusing empty state",
    "Search returns stale results",
    "Mobile layout overflows",
    "Wants dark mode",
]


def _reset() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("web.jsonl", "chat.jsonl"):
        p = STATE_DIR / name
        if p.exists():
            p.unlink()


def _seed_leaf(rng: random.Random, leaf: str, count: int) -> None:
    """Emit ``count`` captured events to one leaf, then triage roughly a third."""
    log_path = STATE_DIR / f"{leaf}.jsonl"
    node_path = f"/feedback/{leaf}"
    captured_ids: list[str] = []

    for _ in range(count):
        e = Event.new(
            type="pmstate.feedback.captured",
            source=node_path,
            data={
                "feedback_id": "",
                "source": leaf,
                "severity": rng.choice(_SEVERITIES),
                "summary": rng.choice(_SUMMARIES),
            },
        )
        e_dict = e.to_dict()
        e_dict["data"]["feedback_id"] = e.id
        append_event(log_path, Event.from_dict(e_dict))
        captured_ids.append(e.id)

    for fid in rng.sample(captured_ids, count // 3):
        append_event(log_path, Event.new(
            type="pmstate.feedback.triaged",
            source=node_path,
            data={
                "feedback_id": fid,
                "category": rng.choice(_CATEGORIES),
                "note": "Reviewed by triage.",
            },
        ))


def main() -> None:
    _reset()
    rng = random.Random(42)
    _seed_leaf(rng, "web", 18)
    _seed_leaf(rng, "chat", 12)
    print(f"Seeded feedback events under {STATE_DIR}")


if __name__ == "__main__":
    main()
