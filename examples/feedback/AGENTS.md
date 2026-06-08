# Feedback context

This is a generic, multi-source feedback subprocess. The agent should help
operators answer questions like *"how much feedback is still open?"*,
*"what's our high-severity backlog?"*, and *"which source is loudest?"*.

## Domain terms

- **Feedback item** — one piece of user-reported feedback. Lifecycle:
  `captured` (open) → `triaged` → `resolved`. Later states override earlier
  ones regardless of arrival order (`resolved` wins over `triaged` wins over
  `captured`).
- **Source** — where the feedback came in. This example has two: `web` and
  `chat`. Each is its own append-only Log leaf.

## Event types

- `pmstate.feedback.captured` — a new item arrived. `data.feedback_id`
  matches the event `id`. Carries `source`, `severity`
  (`low`/`medium`/`high`/`critical`), and a short `summary`.
- `pmstate.feedback.triaged` — an item was reviewed.
  `data.feedback_id` references the original `captured` event's `id`;
  carries `category` and a `note`.
- `pmstate.feedback.resolved` — an item was closed out.
  `data.feedback_id` references the original `captured` event's `id`;
  carries a `resolution`.

## How the rollup reads

Each leaf's `source_view` folds its events into
`{open, triaged, resolved, by_severity}`. The `feedback_rollup` reducer at
`/feedback` sums those across sources and adds:

- `by_severity` — open items grouped by severity, summed across sources.
- `by_source` — open-item count per source (e.g. `{"web": 12, "chat": 8}`).

## Tree shape

```
/  (root: product)
└── /feedback            (rolled up: open, triaged, resolved, by_severity, by_source)
    ├── /feedback/web    (Log: feedback events from the web source)
    └── /feedback/chat   (Log: feedback events from the chat source)
```

Use `list_tree("/")` to orient, then `get_state("/feedback")` for the
rolled-up health view, and `read_log("/feedback/web")` to drill into
individual feedback events.
