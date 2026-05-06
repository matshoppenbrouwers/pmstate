# Procurement context

This is a procurement subprocess for project_alpha. The agent should help
operators answer questions like *"what's pending?"*, *"which vendors are
slowest?"*, and *"are we blocked?"*.

## Domain terms

- **Quote (RFQ response)** — a vendor's price proposal in response to a
  request for quotation. Lifecycle: `received` → either `approved` (good
  to issue an LPO) or `withdrawn` (vendor pulled the offer).
- **LPO (Local Purchase Order)** — the formal commitment to buy. Issued
  *after* a quote is approved. One quote, one LPO.
- **Vendor** — a supplier on the approved-vendor list. Held in
  `state/vendors.json` (Table); slowly-changing reference data.

## What "blocked" means

The procurement reducer sets `blocked: true` when there are more than 5
pending quotes (i.e. `quote.received` events without a matching
`quote.approved` or `quote.withdrawn`). This is a soft warning that
buyer-side review has fallen behind, not a hard error.

## Event types

- `pmstate.quote.received` — vendor submitted a quote. `data.quote_id`
  matches the event `id`.
- `pmstate.quote.approved` — buyer accepted the quote.
  `data.quote_id` references the original `received` event's `id`.
- `pmstate.quote.withdrawn` — vendor pulled the quote.
  `data.quote_id` references the original `received` event's `id`.
- `pmstate.lpo.issued` — formal purchase order cut.
  `data.quote_id` ties it to the approved quote.

## Tree shape

```
/  (root: "active")
└── /procurement              (rolled up: open_quotes, open_lpos, blocked)
    ├── /procurement/quotes   (Log: vendor quote events)
    ├── /procurement/lpos     (Log: LPO events)
    └── /procurement/vendors  (Table: vendor master data)
```

Use `list_tree("/")` to orient, then `get_state("/procurement")` for the
rolled-up health view, and `read_log("/procurement/quotes")` to drill into
individual quote events.
