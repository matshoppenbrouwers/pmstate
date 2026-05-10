# `pmstate` CLI reference

The `pmstate` CLI scaffolds, validates, seeds, and runs a pmstate project
anchored on a `pmstate.yaml` spec file. It calls no LLM — the orchestrating
agent (Claude Code etc.) translates user intent into the spec; the CLI
translates the spec into a working repo. See
[spec-authoring.md](./spec-authoring.md) for the agent-facing spec guide.

## How verbs interact

```
edit pmstate.yaml ──┐
                    ▼
                 init ──> validate ──> seed ──> run
                    │         │         │        │
                    │         │         │        └─ asks the tree a question
                    │         │         └─ generates deterministic seed events
                    │         └─ checks that build_tree() and views compute
                    └─ scaffolds tree.py / views.py / reducers.py / chat.py
                       / add.py / AGENTS.md / state/.gitignore
```

`add.py` is the project-local **write surface** — one sub-command per
event type declared in `pmstate.yaml`. Append a real event with e.g.:

```bash
python add.py candidate-advanced --leaf offers --from interviews --to offers --note "..."
```

## Exit codes

| Code | Meaning                                                                     |
|------|-----------------------------------------------------------------------------|
| 0    | OK                                                                          |
| 1    | User-facing error (no project, broken spec, validation failed, …)           |
| 2    | argparse misuse, unknown verb, or "not yet implemented" stub                |

## `pmstate init`

Scaffold a new project from a `pmstate.yaml` spec.

```
pmstate init [DIR] [--from-spec PATH] [--upgrade] [--force]
```

- `DIR` (positional, default `.`): target directory.
- `--from-spec PATH`: read this spec and write `tree.py`, `views.py`,
  `reducers.py`, `chat.py`, `AGENTS.md`, `pmstate.yaml`, `state/.gitignore`.
- `--upgrade`: re-read the project's existing `pmstate.yaml`, regenerate
  `tree.py`, and append new view/reducer stubs to `views.py` / `reducers.py`
  for spec entries that don't yet exist. Idempotent when the spec is
  unchanged.
- `--force`: overwrite existing files (use with care; trust your git diff).

With no flags and no `pmstate.yaml`, `init` writes `pmstate.example.yaml`
into `DIR` and prints instructions.

### Examples

```
# Bootstrap from scratch
pmstate init                                # writes pmstate.example.yaml
$EDITOR pmstate.example.yaml                # turn it into your spec
mv pmstate.example.yaml pmstate.yaml
pmstate init --from-spec pmstate.yaml .

# Add a node by editing pmstate.yaml then refreshing
pmstate init --upgrade
```

## `pmstate validate`

Check that the project builds cleanly: spec parses, `tree.py` imports,
`build_tree()` returns a `Tree`, `compute_view_at("/")` doesn't raise,
`AGENTS.md` exists.

```
pmstate validate [--strict] [--json]
```

- `--strict`: additionally invoke `mypy` and `ruff` on the project root
  if they're installed. Skips with a `warn` issue when either is absent.
  Never installs anything.
- `--json`: emit issues as a JSON array. Schema:

```json
[{"file": "...", "line": 12, "level": "error", "msg": "..."}]
```

In default (non-`--json`) mode, prints `OK` when there are no errors.
Exit code is 1 iff any `error`-level issue is reported.

## `pmstate seed`

Generate deterministic seed events for every Log leaf in the tree.

```
pmstate seed [--n 30] [--seed 42] [--force]
```

- `--n N`: total events to spread across leaves (default `30`).
- `--seed N`: RNG seed (default `42`). Re-running with the same seed +
  `--force` produces byte-identical files.
- `--force`: required when `state/` already contains non-empty event logs.
  Wipes the existing JSONL files for the matching Log leaves before writing.

Event types come from `pmstate.yaml`'s `events:` block. Payloads are
generated from each event's `schema` dict. Field types: `str`, `int`,
`float`, `bool`. `seed` matches event-type prefixes against leaf names where
possible, otherwise round-robins across all event types.

## `pmstate append`

Append a single event to a Log leaf, with spec-aware validation. Shares the
same validation core as the agent write tool exposed by `pmstate run --write`,
so messages are byte-identical between the two surfaces.

```
pmstate append PATH --type TYPE --data JSON [--source S] [--subject S] [--causationid ID] [--json]
```

| Flag | Description |
|------|-------------|
| `PATH` (positional) | Tree path of the target Log leaf (e.g. `/procurement/quotes`). |
| `--type TYPE` | Event type. Accepts both prefixed (`pmstate.candidate.advanced`) and unprefixed (`candidate.advanced`) forms. |
| `--data JSON` | Event payload as a JSON object. Pass `-` to read JSON from stdin. |
| `--source S` | Override the event `source`. Defaults to `PATH`. |
| `--subject S` | Optional event `subject`. |
| `--causationid ID` | Optional causation id (links to a parent event). |
| `--json` | Emit JSON output (success object or issue array) instead of text. |

### Exit codes

`0` on success. `1` on validation error, missing project, JSON parse error, or
write failure.

### `--json` shape

On success:
```json
{"id": "01J...ULID", "path": "/abs/path/state/quotes.jsonl", "bytes": 312}
```

On failure (validation or JSON parse):
```json
[{"file": "<append>", "line": null, "level": "error", "msg": "..."}]
```

The failure shape matches `pmstate validate --json` (same `Issue` schema) so
agents can reuse one parser.

### Examples

```bash
# Explicit form
pmstate append /procurement/quotes --type quote.received \
  --data '{"vendor":"acme","amount":100,"currency":"USD"}'

# Stdin form (useful when piping from a generator)
echo '{"vendor":"beta","amount":50,"currency":"EUR"}' \
  | pmstate append /procurement/quotes --type quote.received --data -
```

## `pmstate run`

Dispatch a one-shot prompt to `Harness.run` against the project tree.

```
pmstate run [PROMPT] [--watch | --no-watch]
```

- `PROMPT` (positional, optional): the prompt to send. If omitted and
  stdin is not a tty, the prompt is read from stdin.
- `--watch` / `--no-watch`: enable / disable the filesystem watcher.
  Default: `--no-watch`.

Loads `tree.py:build_tree()` from the project root, instantiates
`pmstate.adapters.claude_sdk.Harness`, and prints the reply to stdout.
Requires the optional `claude-sdk` extra and an `ANTHROPIC_API_KEY`.
