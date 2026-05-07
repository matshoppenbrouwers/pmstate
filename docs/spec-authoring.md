# Authoring a `pmstate.yaml` spec

This document is written for an LLM agent (Claude Code, Cursor, codex,
etc.) translating a user's natural-language request into a `pmstate.yaml`
file. It is the load-bearing document of the pmstate CLI: keep it open
while you work, and follow the recipe at the end.

## What is a `pmstate.yaml`

A `pmstate.yaml` is the declarative spec for one pmstate project. It
describes the tree of `Node`s, names each leaf's storage type (`log` /
`table` / `none`), declares the event types the tree emits, and pins the
pmstate version. Running `pmstate init --from-spec pmstate.yaml DIR`
turns it into a working project.

## Schema reference

```yaml
name: <project-name>            # str, required. Surfaces in agent context.
pmstate_version: "<version>"    # str, required. e.g. "0.2.0"
tree:                           # required mapping
  root: <root-node-name>        # str, required. Name of the root Node.
  nodes:                        # list[mapping], required (may be empty)
    - path: /<root>/<...>       # str, required. POSIX-shaped, ≥ 2 segments.
      reducer: <fn-name>        # str, optional. Names a function in reducers.py.
      children:                 # list[mapping], required (may be empty).
        - name: <leaf-name>     # str, required.
          state: log|table|none # required. log → JSONL, table → JSON, none → no state.
          view: <fn-name>       # str, optional. Names a function in views.py.
          reducer: <fn-name>    # str, optional. Per-child reducer (rare).
events:                         # mapping. Optional, default {}.
  <type>:                       # e.g. candidate.added
    schema:                     # mapping str → str. type names: 'str','int','float','bool'.
      <field>: <type>
```

**Constraints:**

- `path` must start with `/` and contain ≥ 2 segments (root + child).
- `path[0]` must equal `tree.root`.
- `state` must be one of `log`, `table`, `none`.
- `view` and `reducer` are bare identifiers — the CLI generates a stub of
  that name in `views.py` / `reducers.py`. Keep them snake_case.
- Unknown keys at any level are an error (the spec is intentionally narrow).

## Three worked examples

### 1. Linear pipeline (hiring funnel)

User prompt: *"Track our Q3 hiring pipeline: leads, screened candidates,
interviews, offers, hires."*

```yaml
name: hiring-pipeline
pmstate_version: "0.2.0"
tree:
  root: active
  nodes:
    - path: /active/pipeline
      reducer: pipeline_rollup
      children:
        - {name: leads,      state: log, view: bucket_view}
        - {name: screened,   state: log, view: bucket_view}
        - {name: interviews, state: log, view: bucket_view}
        - {name: offers,     state: log, view: bucket_view}
        - {name: hires,      state: log, view: bucket_view}
events:
  candidate.added:
    schema: {name: str, source: str}
  candidate.advanced:
    schema: {from: str, to: str, note: str}
```

What this gets you: a five-bucket funnel with rollup. Agent can answer
*"how many candidates are at each stage?"* by reading each leaf's view.

### 2. Kanban-style with `blocked` rollup

User prompt: *"I want a kanban board: todo, doing, done. Tell me when
something's blocked for too long."*

```yaml
name: kanban
pmstate_version: "0.2.0"
tree:
  root: board
  nodes:
    - path: /board/lanes
      reducer: blocked_rollup
      children:
        - {name: todo,  state: log, view: lane_view}
        - {name: doing, state: log, view: lane_view}
        - {name: done,  state: log, view: lane_view}
events:
  card.created:
    schema: {title: str, owner: str}
  card.moved:
    schema: {card_id: str, to: str}
  card.blocked:
    schema: {card_id: str, reason: str}
```

What this gets you: three lanes plus a `blocked_rollup` that flags
boards in trouble.

### 3. Log + rollup hierarchy (procurement)

User prompt: *"I'm running procurement: track quotes from vendors, the
LPOs we cut after approving them, and the vendor master list."*

```yaml
name: project_alpha
pmstate_version: "0.2.0"
tree:
  root: active
  nodes:
    - path: /active/procurement
      reducer: procurement_rollup
      children:
        - {name: quotes,  state: log,   view: quote_view}
        - {name: lpos,    state: log,   view: lpo_view}
        - {name: vendors, state: table}
events:
  quote.received:
    schema: {quote_id: str, vendor: str, amount: float}
  quote.approved:
    schema: {quote_id: str}
  quote.withdrawn:
    schema: {quote_id: str}
  lpo.issued:
    schema: {quote_id: str, lpo_number: str}
```

What this gets you: two append-only event logs (quotes, lpos), one slowly-
changing reference table (vendors), and a parent reducer that says
*"we're blocked when there are more than 5 open quotes"*.

## The 5-rule recipe (NL → YAML)

Walk the user's words once and answer these five questions:

1. **What are the buckets?** Each distinct status, stage, or category
   the user names becomes a child `Node` under one parent.

2. **Stream or snapshot?** For each bucket, ask:
   - "Does the user think of this as *events that happen*?" → `state: log`.
   - "Does the user think of this as *what's currently true*?" → `state: table`.
   - "Is this just a grouping label with no data?" → `state: none`.

3. **Name event types.** Use `subject.verb-past-tense`:
   `candidate.added`, `quote.received`, `card.moved`. The CLI prefixes
   these with `pmstate.` automatically when seeding.

4. **Add a reducer when the user mentions roll-up, aggregation, or
   "is X blocked?"** — anything that summarizes children into a parent
   view. Otherwise leave reducer off.

5. **Pin `pmstate_version`** to the version installed in the project
   (currently `"0.2.0"`). This is read by `init --upgrade`.

## Common pitfalls

- **Naming a node `state` shadows the schema keyword.** Rename it.
- **Forgetting `pmstate_version`.** It's required.
- **Path doesn't start with the root segment.** `path: /active/pipeline`
  with `root: active` is correct; `path: /pipeline` is rejected.
- **Defining a `view` that no leaf references.** Harmless but the stub is
  unused — drop it from the spec.
- **Two children with the same `name`.** Rejected at tree construction.
- **Event payloads with non-flat schemas.** v1 supports `field: str-type`
  only. Nest later if you need it (backlog).
