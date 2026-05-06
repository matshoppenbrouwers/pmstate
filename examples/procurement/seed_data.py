"""Generate ~50 deterministic procurement events under examples/procurement/state/.

Run with::

    python -m examples.procurement.seed_data

Reproducible (seed=42), idempotent (deletes existing state files first).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from pmstate import Event, append_event

STATE_DIR = Path(__file__).parent / "state"

_VENDORS = [
    "Acme Hardware", "Bluefin Logistics", "Cobalt Print",
    "Delta Catering", "Elm Office Supplies", "Foxtrot Travel",
]


def _reset() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("quotes.jsonl", "lpos.jsonl"):
        p = STATE_DIR / name
        if p.exists():
            p.unlink()


def _write_vendors() -> None:
    payload = {v: {"approved": True, "country": "KE"} for v in _VENDORS}
    (STATE_DIR / "vendors.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _emit(rng: random.Random) -> None:
    quotes = STATE_DIR / "quotes.jsonl"
    lpos = STATE_DIR / "lpos.jsonl"
    quote_ids: list[str] = []

    for _ in range(30):
        vendor = rng.choice(_VENDORS)
        amount = rng.randint(500, 8000)
        e = Event.new(
            type="pmstate.quote.received",
            source="/procurement/quotes",
            data={"vendor": vendor, "amount": amount, "quote_id": ""},
        )
        e_dict = e.to_dict()
        e_dict["data"]["quote_id"] = e.id
        append_event(quotes, Event.from_dict(e_dict))
        quote_ids.append(e.id)

    approved_ids = rng.sample(quote_ids, 15)
    for qid in approved_ids:
        append_event(quotes, Event.new(
            type="pmstate.quote.approved",
            source="/procurement/quotes",
            data={"quote_id": qid},
        ))

    not_approved = [q for q in quote_ids if q not in set(approved_ids)]
    for qid in rng.sample(not_approved, min(3, len(not_approved))):
        append_event(quotes, Event.new(
            type="pmstate.quote.withdrawn",
            source="/procurement/quotes",
            data={"quote_id": qid},
        ))

    for qid in rng.sample(approved_ids, 10):
        append_event(lpos, Event.new(
            type="pmstate.lpo.issued",
            source="/procurement/lpos",
            data={"quote_id": qid, "lpo_number": f"LPO-{rng.randint(1000, 9999)}"},
        ))


def main() -> None:
    _reset()
    _write_vendors()
    _emit(random.Random(42))
    print(f"Seeded events under {STATE_DIR}")


if __name__ == "__main__":
    main()
