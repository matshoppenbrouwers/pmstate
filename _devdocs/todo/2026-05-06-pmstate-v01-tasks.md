# pmstate v0.1 — Task Plan

**Plan source:** `_devdocs/plans/2026-05-06-pmstate-v01-implementation.md`
**Goal:** Ship pmstate 0.1.0 to PyPI with one real Laterite procurement process running end-to-end.

**Read first (every task references this):**
- `_devdocs/plans/2026-05-06-pmstate-v01-implementation.md` — full plan, including the **"Code quality standard (applies to every phase)"** section. Every task's "production-grade check" lives there.
- `_devdocs/research/2026-05-06-pmstate-internal-design.md` — Q1–Q7 design decisions.
- `_devdocs/research/2026-05-06-pmstate-external-validation.md` — locked decisions and refinements.

---

## Parallelization Guide

```
P0-1 -> P0-2 +-> P0-7 -> P0-8(manual)
        P0-3 +
        P0-4 +
        P0-5 +
        P0-6 +
            -> P1-1 -> P1-3 -> P1-4
               P1-2 +
                    -> P2-1 -> P2-2 -> P2-3 -> P2-4 -> P2-5 -> P2-6
                                                            -> P3-1 -> P3-2
                                                                    -> P4-1 -> P4-3 -> P4-5
                                                                       P4-2 +
                                                                       P4-4 +
                                                                            -> P5-1 -> P5-2
                                                                                    -> P6-1 -> P6-2 -> P6-3
                                                                                            -> P7-1 -> P7-3 -> P7-5
                                                                                               P7-2 +
                                                                                               P7-4 +
```

### Tag legend

| Tag | Meaning |
|-----|---------|
| `[seq]` | Must complete before next task starts |
| `[parallel-after:X]` | Can run parallel with siblings after task X |
| `[manual]` | Mats does this, not Claude |
| `[ ]` | Not started |
| `[x]` | Completed |

### Parallel opportunities

- **P0-2..P0-6** parallel after P0-1 (different files, no shared state)
- **P1-1 + P1-2** parallel after P0-7 (storage.py vs _paths.py — independent)
- **P4-2 + P4-4** parallel after P4-1 (tree.py vs agents_md.py — different concerns)
- **P7-2 + P7-4** parallel after P7-1 (example seed data vs integration test fixtures)

### Per-phase intermezzo

After every phase: run full test suite (`uv run pytest -v --cov=pmstate --cov-fail-under=80`), confirm green, walk the **production-grade check** from the plan. Don't proceed to the next phase if anything fails.

---

# Phase 0: Repo skeleton + PyPI placeholder

**Plan ref:** `_devdocs/plans/2026-05-06-pmstate-v01-implementation.md` § "Phase 0"

### [P0-1] [seq] [x] P1: Bootstrap pyproject.toml + LICENSE + .gitignore

**Files:** `pyproject.toml`, `LICENSE`, `.gitignore`

**Instructions:**
- Create `pyproject.toml` with PEP 621 `[project]` table, `name = "pmstate"`, `version = "0.0.1"`, `requires-python = ">=3.11"`, dynamic version disabled (single-source via `__init__.py` until 0.1.0).
- Declare runtime deps: `attrs>=23.2`, `python-ulid>=2.7`, `watchfiles>=0.24`.
- Declare optional deps under `[project.optional-dependencies]`: `claude-sdk = ["claude-agent-sdk>=...]"`, `dev = ["pytest>=8", "pytest-cov>=5", "hypothesis>=6.100", "ruff>=0.6", "mypy>=1.11", "build>=1.2", "twine>=5"]`.
- Use `hatchling` as build backend; configure `[tool.hatch.build.targets.wheel]` with `packages = ["src/pmstate"]`.
- Create MIT `LICENSE` (Mats Hoppenbrouwers, 2026).
- Append to `.gitignore`: `dist/`, `*.egg-info/`, `.venv/`, `.coverage`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `htmlcov/`.

**Accept:** `uv sync` and `uv build` both succeed against an empty source tree (after P0-5 lands `src/pmstate/__init__.py`); no extra files committed accidentally.

**Test:** `uv build && ls dist/ | grep -E 'pmstate-0.0.1.(tar.gz|whl)'`

---

### [P0-2] [parallel-after:P0-1] [x] P1: Tooling configs (ruff, mypy, pytest)

**Files:** `ruff.toml`, `mypy.ini`, `pyproject.toml` (`[tool.pytest.ini_options]` section only)

**Instructions:**
- `ruff.toml`: `line-length = 100`, `target-version = "py311"`, `select = ["E", "F", "I", "UP", "B", "SIM", "RUF", "PL"]`. Disable `PLR0913` (too many args — false positives on builders).
- `mypy.ini`: `strict = True`, `python_version = 3.11`, `warn_redundant_casts = True`, `warn_unused_ignores = True`, exclude `tests/` from strict-mode noisy rules but keep type-checking on.
- Add to `pyproject.toml`: `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `addopts = "--cov=pmstate --cov-report=term-missing --cov-fail-under=80 --strict-markers"`.

**Accept:** `uv run ruff check src tests` and `uv run mypy src` both run with zero output on an empty tree (after P0-5).

**Test:** `uv run ruff check . && uv run mypy src`

---

### [P0-3] [parallel-after:P0-1] [x] P1: CI workflow

**Files:** `.github/workflows/ci.yml`

**Instructions:**
- GitHub Actions workflow triggered on push to `main` and on PRs.
- Matrix: Python 3.11, 3.12, 3.13 on `ubuntu-latest`.
- Steps: checkout, install `uv`, `uv sync --all-extras`, `uv run ruff check .`, `uv run mypy src`, `uv run pytest`.
- Cache `uv` dependencies via `setup-python` cache or `actions/cache` keyed on `pyproject.toml` hash.
- Fail fast: false (let all matrix entries report).

**Accept:** Pushed to a draft PR, all three Python versions pass the green-tree CI run.

**Test:** Pushed branch shows three green check marks in GitHub PR view.

---

### [P0-4] [parallel-after:P0-1] [x] P1: Repo-root AGENTS.md + minimal README

**Files:** `AGENTS.md`, `README.md`

**Instructions:**
- `AGENTS.md` (≤ 40 lines): one-paragraph project overview, build commands (`uv sync`, `uv run pytest`, `uv build`), explicit pointer "humans and AI agents read this first", reference to `_devdocs/` for design.
- `README.md` (80–120 lines): Backlog.md-style framing — lead with "the directory tree IS the process state". Include the 28-LOC procurement example verbatim from `_devdocs/research/2026-05-06-pmstate-external-validation.md` § 4. End with "open but not supported, one user, API will break, stars welcome."
- No badges yet (PyPI/CI badges added in P7-5 with the 0.1.0 release).

**Accept:** Both files render correctly on GitHub; example in README is copy-paste runnable after Phase 7 lands.

**Test:** `wc -l README.md AGENTS.md` — README between 80 and 120 lines, AGENTS.md ≤ 40.

---

### [P0-5] [parallel-after:P0-1] [x] P1: Package skeleton

**Files:** `src/pmstate/__init__.py`, `src/pmstate/py.typed`, `tests/__init__.py`, `tests/conftest.py`

**Instructions:**
- `src/pmstate/__init__.py`: single line `__version__ = "0.0.1"`. No re-exports yet (added per phase as modules land).
- `src/pmstate/py.typed`: empty marker file (PEP 561 inline-type-info advertisement so consumers' mypy picks up our stubs).
- `tests/__init__.py`: empty.
- `tests/conftest.py`: empty for now; reserved for `tmp_path` fixtures and fake-time helpers added in later phases.

**Accept:** `python -c "import pmstate; print(pmstate.__version__)"` prints `0.0.1` from a fresh `uv sync`.

**Test:** `uv run python -c "import pmstate; assert pmstate.__version__ == '0.0.1'"`

---

### [P0-6] [parallel-after:P0-1] [x] P2: Pre-commit hooks (optional)

**Files:** `.pre-commit-config.yaml`

**Instructions:**
- Install `pre-commit` hooks for `ruff format`, `ruff check --fix`, `mypy` (warning-only on staged files), and trailing-whitespace.
- Add `uv run pre-commit install` to AGENTS.md setup section.

**Accept:** `pre-commit run --all-files` exits zero on the empty tree.

**Test:** `uv run pre-commit run --all-files`

---

### [P0-7] [seq] [x] P1: Build + fresh-venv install verification

**Files:** none (verification only)

**Instructions:**
- After P0-1..P0-6 land, run `uv build` and confirm `dist/` contains both `.tar.gz` and `.whl`.
- In a separate `python -m venv /tmp/pmstate-verify && source /tmp/pmstate-verify/bin/activate && pip install dist/pmstate-0.0.1-py3-none-any.whl`, confirm `python -c "import pmstate; print(pmstate.__version__)"` prints `0.0.1`.
- Push to a draft PR, confirm CI matrix green across all three Python versions.

**Accept:** Distribution wheel installs cleanly in an isolated venv; CI passes.

**Test:** Manual fresh-venv flow above + GitHub Actions green.

---

### [P0-8] [manual] [ ] P1: Mats — register `pmstate` on PyPI (placeholder upload)

**Files:** none (manual action by Mats)

**Instructions:**
- Mats only. Steps:
  1. Create PyPI account at <https://pypi.org/account/register/> if needed.
  2. Generate API token at <https://pypi.org/manage/account/token/> (scope: entire account for first upload, then narrow).
  3. From repo root: `uv build`, then `uv publish` (or `twine upload dist/*` with `__token__` username + token as password).
  4. Verify `https://pypi.org/project/pmstate/` shows version 0.0.1.
- Optional dry-run via TestPyPI first: `uv publish --publish-url https://test.pypi.org/legacy/`.

**Accept:** `pmstate` reserved on PyPI as 0.0.1; `pip install pmstate` in a fresh venv works.

**Test:** `python -m venv /tmp/pyiptest && /tmp/pyiptest/bin/pip install pmstate && /tmp/pyiptest/bin/python -c "import pmstate; print(pmstate.__version__)"`

---

# Phase 1: Core primitives — Node, Log, Table

**Plan ref:** § "Phase 1"

### [P1-1] [seq] [ ] P1: Implement Log + Table storage helpers

**Files:** `src/pmstate/storage.py`, `tests/unit/test_storage.py`

**Instructions:**
- Implement `Log(path: str | Path, *, view: Callable[[Iterable[dict]], dict] | None = None)` and `Table(path: str | Path, *, view: Callable[[Any], dict] | None = None)` as `attrs.@define(frozen=True, slots=True)` classes.
- Both expose `.read() -> dict` returning the view dict.
- `Log.read()` default view returns `{"count": int, "latest": dict | None, "first": dict | None}`. Read JSONL with bounded buffer (don't load all rows when computing count — `latest` requires last row only; consider tail-reading). For now, simple full-file read is acceptable; document the cost in a one-line comment.
- `Table.read()` default view: parse JSON file, truncate above 2 KiB serialized OR 50 top-level keys, whichever first. Include a `_truncated: True` marker when truncation kicks in.
- Wrap user view functions with error capture: any exception → return `{"error": str(exc), "exception": type(exc).__name__, "path": str(self.path)}`. Errors-as-data per Q5.
- Tests: empty file, single row, default views, custom views, truncation, error capture, missing file (returns `{"error": ..., "exception": "FileNotFoundError"}`).

**Accept:** Public-grade-check (plan §) passes; tests give ≥ 90 % coverage of `storage.py`.

**Test:** `uv run pytest tests/unit/test_storage.py -v --cov=pmstate.storage --cov-fail-under=90`

---

### [P1-2] [parallel-after:P0-7] [ ] P1: Implement path resolver

**Files:** `src/pmstate/_paths.py`, `tests/unit/test_paths.py`

**Instructions:**
- Internal helper: `parse(path: str) -> tuple[str, ...]` ("/active/procurement/quotes" → `("active", "procurement", "quotes")`). Empty/`/` → `()`. Validate: no empty segments, no leading whitespace.
- `format(parts: tuple[str, ...]) -> str` (round-trip with `parse`).
- `NodePathError` exception class with the offending path in the message.
- Tests via `hypothesis`: round-trip property `format(parse(p)) == p` for any valid path; `parse` rejects invalid (`""`, `//`, `/a//b`, `a/b` without leading slash).

**Accept:** Hypothesis property test passes 200 examples; explicit error cases each have a unit test.

**Test:** `uv run pytest tests/unit/test_paths.py -v`

---

### [P1-3] [seq] [ ] P1: Implement Node primitive

**Files:** `src/pmstate/node.py`, `tests/unit/test_node.py`

**Instructions:**
- `Node` as `attrs.@define(frozen=True, slots=True)` with the field order from the plan: `name`, `state` (Log | Table | None), `view`, `reducer`, `children` (tuple for hashability), `description`.
- Validators (run at construction): `name` non-empty + no `/`; `children` is a tuple; sibling names within `children` are unique (raise `ValueError` with the duplicate); if `state` is set, `view` may also be set; if `view` is set, must be callable; same for `reducer`.
- Convenience: `Node(...)` accepts `children: Iterable[Node]` and freezes to `tuple` internally.
- `description` falls back to `view.__doc__` *lazily* — provide a property `effective_description` rather than computing at construction (avoids reading attributes on `view=None` nodes).
- `find(self, path: str) -> Node` walks the subtree using `_paths.parse`. Raises `NodePathError` on miss.
- Tests: construction happy paths, invalid name, duplicate sibling names, frozen-mutation rejection, `find` happy + miss, `effective_description` fallback chain.

**Accept:** Procurement subtree from plan § "Phase 7" example constructs in REPL: `Node("procurement", children=[Node("quotes"), Node("lpos"), Node("vendors")])`. `node.find("/quotes")` returns the right child.

**Test:** `uv run pytest tests/unit/test_node.py -v`

---

### [P1-4] [seq] [ ] P1: Wire __init__ re-exports

**Files:** `src/pmstate/__init__.py`, `tests/unit/test_public_api.py`

**Instructions:**
- Re-export `Node`, `Log`, `Table`, `NodePathError` from `pmstate`.
- No wildcard imports; explicit name list. `__all__ = ["Node", "Log", "Table", "NodePathError"]`.
- Test: `import pmstate; pmstate.Node, pmstate.Log, pmstate.Table, pmstate.NodePathError` resolve.

**Accept:** `from pmstate import Node, Log, Table` works at runtime; `__all__` list is accurate.

**Test:** `uv run pytest tests/unit/test_public_api.py -v`

---

# Phase 2: Event envelope, writer, reader

**Plan ref:** § "Phase 2"

### [P2-1] [seq] [ ] P1: ULID wrapper

**Files:** `src/pmstate/_ulid.py`, `tests/unit/test_ulid.py`

**Instructions:**
- Thin module: `def new() -> str` returns a 26-char Crockford-base32 ULID via `python-ulid`. `def parse(value: str) -> ULID` validates a string.
- `is_valid(value: str) -> bool` for cheap pre-checks.
- Tests: 1000 sequential generations are all unique; sortable lexicographically (within ms precision, monotonicity holds inside one process); `parse` rejects bad inputs.

**Accept:** Hypothesis test confirms uniqueness over 5000 calls in a single process.

**Test:** `uv run pytest tests/unit/test_ulid.py -v`

---

### [P2-2] [seq] [ ] P1: Event envelope (CloudEvents-shaped)

**Files:** `src/pmstate/envelope.py`, `tests/unit/test_envelope.py`

**Instructions:**
- `Event` as `attrs.@define(frozen=True, slots=True)` with the locked fields: `specversion: str = "1.0"` (default), `id: str` (ULID), `source: str`, `type: str`, `time: str`, `subject: str | None = None`, `data: dict | None = None`, `causationid: str | None = None`.
- Factory: `Event.new(*, type: str, source: str, data: dict | None = None, subject: str | None = None, causationid: str | None = None) -> Event`. Generates `id` via `_ulid.new()`, `time` via `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"` (millisecond precision, trailing Z).
- `to_dict() -> dict` and `from_dict(d: dict) -> Event` — round-trip preserves all fields.
- Validators: `type` matches `^pmstate\.[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+(\.v\d+)?$` regex (dotted, lowercase, optional `.vN` suffix); `source` starts with `/`.
- Tests: round-trip via `to_dict` → `from_dict`; type-regex happy/sad paths; ms-precision time format; CloudEvents JSON shape (verified by parsing into a generic dict and asserting keys).

**Accept:** Round-trip property test (hypothesis) passes; `Event.new(type="pmstate.quote.received", source="/active/procurement/quotes", data={"vendor": "X"})` produces a valid envelope.

**Test:** `uv run pytest tests/unit/test_envelope.py -v`

---

### [P2-3] [seq] [ ] P1: Append-only writer

**Files:** `src/pmstate/writer.py`, `tests/unit/test_writer.py`

**Instructions:**
- `EventTooLargeError(Exception)`: carries the offending size.
- `append_event(log_path: Path, event: Event, *, fsync: bool = False) -> None`. Serializes via `json.dumps(event.to_dict(), separators=(",", ":"), ensure_ascii=False) + "\n"`. Computes UTF-8 byte length; raises `EventTooLargeError` if > 4000.
- Opens `log_path` with `open(log_path, "ab")`; writes the encoded bytes in one `write()` call. Optional `fsync` calls `os.fsync(f.fileno())` before close.
- Creates parent directories on demand (`log_path.parent.mkdir(parents=True, exist_ok=True)`).
- Tests: append 1000 events, read back via plain `open(...).readlines()`, assert order + count. Oversized payload raises `EventTooLargeError`. Atomicity smoke test: spawn 10 threads each appending 100 events to the same file (sanity check; v0.1 contract is single-writer, but smoke confirms the write path itself doesn't tear lines).

**Accept:** All tests green; reading a 1000-event log yields 1000 valid JSON dicts in append order.

**Test:** `uv run pytest tests/unit/test_writer.py -v`

---

### [P2-4] [parallel-after:P2-3] [ ] P1: Reader with byte-cursor replay

**Files:** `src/pmstate/reader.py`, `tests/unit/test_reader.py`

**Instructions:**
- `read_events(log_path: Path, *, start: int | None = None, end: int | None = None, limit: int | None = None, filter: Callable[[dict], bool] | None = None) -> Iterator[dict]`. `start`/`end` are byte offsets (for replay/cursor patterns). `limit` caps yielded rows. `filter` is post-decode predicate.
- Stream line-by-line; do not load whole file into memory. Skip blank lines silently.
- On a JSON-decode error, raise `ReaderError(path, line_number, raw_line)` with explicit context.
- Upcaster hook: accepts `registry: UpcasterRegistry | None = None` parameter; passes each decoded dict through `registry.upcast(d)` if registry is provided. Default behaviour (no registry) returns dicts as-is. (Phase 3 lands the registry; this hook keeps that integration clean.)
- Tests: read all, byte-range slice, limit truncates, filter excludes, malformed line raises with line number, empty file yields nothing.

**Accept:** Reader iterates without loading whole file; byte-range replay returns the right slice; tests cover the four parameters.

**Test:** `uv run pytest tests/unit/test_reader.py -v`

---

### [P2-5] [seq] [ ] P1: Hypothesis property tests for envelope round-trip

**Files:** `tests/unit/test_envelope_properties.py`

**Instructions:**
- Hypothesis strategies for valid `Event` field values.
- Property: write any event, read it back via `read_events`, decoded dict equals `event.to_dict()`.
- Property: 1000 ULIDs from concurrent `Event.new(...)` calls are all unique (single-process; cross-machine is out of scope).
- Property: appending N events then reading with `limit=k` yields exactly `min(N, k)` rows.

**Accept:** All three properties pass with `--hypothesis-show-statistics`.

**Test:** `uv run pytest tests/unit/test_envelope_properties.py -v --hypothesis-show-statistics`

---

### [P2-6] [seq] [ ] P1: Wire __init__ re-exports for events

**Files:** `src/pmstate/__init__.py`

**Instructions:**
- Add `Event`, `append_event`, `read_events`, `EventTooLargeError`, `ReaderError` to re-exports + `__all__`.
- Verify: `from pmstate import Event, append_event, read_events, EventTooLargeError`.

**Accept:** Public API test (extended from P1-4) passes with new names.

**Test:** `uv run pytest tests/unit/test_public_api.py -v`

---

# Phase 3: Upcaster registry

**Plan ref:** § "Phase 3"

### [P3-1] [seq] [ ] P1: UpcasterRegistry

**Files:** `src/pmstate/upcasters.py`, `tests/unit/test_upcasters.py`

**Instructions:**
- `Upcaster` type alias: `Callable[[dict], dict]`.
- `UpcasterRegistry` class with `.register(from_type: str, fn: Upcaster) -> None` (rejects duplicate registration with `ValueError`) and `.upcast(event_dict: dict) -> dict` (loops while `event_dict["type"]` has a registered upcaster; cycle detection: if same type seen twice in chain, raise `UpcastCycleError`).
- Module-level `default_registry = UpcasterRegistry()`.
- Tests: register one upcaster, single-step transform; chain of three upcasters; cycle detection; missing key (no transform).

**Accept:** Cycle detection raises; chain transforms through 3 hops; `default_registry` is the same singleton across imports.

**Test:** `uv run pytest tests/unit/test_upcasters.py -v`

---

### [P3-2] [seq] [ ] P1: Wire reader to use registry + re-exports

**Files:** `src/pmstate/reader.py`, `src/pmstate/__init__.py`, `tests/unit/test_reader_with_upcasters.py`

**Instructions:**
- `read_events` uses `default_registry` when `registry` parameter is `None`.
- Add `UpcasterRegistry`, `default_registry`, `Upcaster`, `UpcastCycleError` to `__init__.py` re-exports.
- Integration test: write events with `type="pmstate.quote.received"`, register an upcaster transforming to `pmstate.quote.received.v2` adding a default field, read the log, verify all rows emerge as v2.

**Accept:** Integration test passes; upcasters work transparently through `read_events`.

**Test:** `uv run pytest tests/unit/test_reader_with_upcasters.py -v`

---

# Phase 4: Rollup, content-hash invalidation, Tree, AGENTS.md

**Plan ref:** § "Phase 4"

### [P4-1] [seq] [ ] P1: Rollup + content-hash cache

**Files:** `src/pmstate/rollup.py`, `tests/unit/test_rollup.py`

**Instructions:**
- `compute_view(node: Node, root: Path) -> dict`. For leaves with `state`: call `state.read()`. For internal nodes: recursively compute children's views into a `dict[str, dict]` keyed by child name; if `node.reducer` is set, call it; else return the children dict (generic dump default).
- Wrap reducer calls with the same error-as-data pattern as views.
- `_view_fn_hash(fn: Callable | None) -> str`: stable hash of `inspect.getsource(fn)` after stripping comments/whitespace; falls back to `f"id:{id(fn)}"` if source not available. SHA-256 hex.
- `_cache_key(node, root, children_hashes: tuple[str, ...]) -> str`: `(node_path, view_fn_hash, reducer_fn_hash, children_hashes)` joined and SHA-256-hex'd.
- Persistent cache at `<node-on-disk>/.pmstate/rollup.json` keyed by `_cache_key`. On read: if stored key matches fresh key → return cached view; else recompute, persist, return.
- Tests: cache hit (no recompute), cache miss after child file change, generic-dump default, custom reducer, error-in-view → error view propagates as data, error-in-reducer → reducer-error view.
- Document the **Hamilton nested-call hash gotcha** in the module docstring AND in the `compute_view` docstring (per plan §4 design notes).

**Accept:** Cache invalidates on child JSONL append; generic dump works without a reducer; reducer errors surface as data, not exceptions.

**Test:** `uv run pytest tests/unit/test_rollup.py -v`

---

### [P4-2] [parallel-after:P4-1] [ ] P1: Tree wrapper with spawn/prune

**Files:** `src/pmstate/tree.py`, `tests/unit/test_tree.py`

**Instructions:**
- `Tree(name: str, root: Node)` as `attrs.@define(frozen=True, slots=True)`. Fields: `name`, `root`.
- `Tree.get(path: str) -> Node`: delegates to `Node.find`.
- `Tree.spawn(parent_path: str, child: Node) -> Tree`: returns a new `Tree` with `child` added under `parent_path`. Refuses duplicate sibling names (raises `ValueError`).
- `Tree.prune(path: str) -> Tree`: returns a new `Tree` with the named node removed. Refuses non-existent paths (raises `NodePathError`).
- Implementation: walk to parent, replace its `children` tuple with a new tuple, rebuild the path back to root via `attrs.evolve`.
- Tests: spawn happy + duplicate-sibling sad; prune happy + missing sad; round-trip (spawn then prune yields original tree, modulo Node identity).

**Accept:** Spawn/prune are symmetric (no half-mutability trap); both return new `Tree` snapshots; original tree unchanged.

**Test:** `uv run pytest tests/unit/test_tree.py -v`

---

### [P4-3] [seq after P4-2] [ ] P2: Persistent rollup cache integration with Tree

**Files:** `src/pmstate/rollup.py`, `tests/unit/test_rollup_with_tree.py`

**Instructions:**
- Extend `compute_view` to accept a `Tree` and a path: `compute_view_at(tree: Tree, path: str, root_dir: Path) -> dict`.
- Verify cache files land at the right disk location relative to `root_dir`.
- Verify spawn/prune correctly invalidates the cache (because `_cache_key` includes children_hashes which change when a child appears/disappears).
- Tests: spawn a child → parent rollup recomputes; prune a child → parent rollup recomputes; sibling change does not invalidate unrelated branches.

**Accept:** Spawn/prune triggers rollup invalidation transitively up the path.

**Test:** `uv run pytest tests/unit/test_rollup_with_tree.py -v`

---

### [P4-4] [parallel-after:P4-1] [ ] P2: AGENTS.md loader

**Files:** `src/pmstate/agents_md.py`, `tests/unit/test_agents_md.py`

**Instructions:**
- `load_agents_md(tree_root: Path) -> str | None`: reads `<tree_root>/AGENTS.md` if present, returns content. Returns `None` if missing. Raises if exists but unreadable.
- Cache result keyed on file mtime so repeated calls within a session don't re-read.
- Tests: present file returns content; absent file returns `None`; unreadable file raises `OSError`; mtime change invalidates cache.

**Accept:** Loader handles all three states (present/absent/unreadable) cleanly.

**Test:** `uv run pytest tests/unit/test_agents_md.py -v`

---

### [P4-5] [seq] [ ] P1: Wire __init__ re-exports for Phase 4

**Files:** `src/pmstate/__init__.py`, `tests/unit/test_public_api.py`

**Instructions:**
- Re-export `Tree`, `compute_view`, `compute_view_at`, `load_agents_md`.
- Update `__all__`.
- Extend `test_public_api.py` to assert the new names resolve.

**Accept:** `from pmstate import Tree, compute_view, compute_view_at, load_agents_md` works.

**Test:** `uv run pytest tests/unit/test_public_api.py -v`

---

# Phase 5: Agent tools surface

**Plan ref:** § "Phase 5"

### [P5-1] [seq] [ ] P1: The four tools

**Files:** `src/pmstate/tools.py`, `tests/unit/test_tools.py`

**Instructions:**
- `list_tree(tree: Tree, path: str = "/", depth: int = 1) -> list[dict]`: returns `[{"name": str, "description": str | None, "has_state": bool, "has_children": bool, "type": "leaf" | "internal"}, ...]` for each direct child at `path`. `depth > 1` recurses; cap at 3 (raise `ValueError` above).
- `get_state(tree: Tree, path: str, root_dir: Path) -> dict`: delegates to `compute_view_at`. Errors-as-data (not exceptions).
- `find_state(tree: Tree, query: str, *, path_glob: str | None = None, max_results: int = 50, root_dir: Path) -> list[dict]`: walk tree breadth-first, compute view per node, JSON-search for `query` substring in serialized view, return up to `max_results` `{"path": ..., "snippet": ...}` matches.
- `read_log(tree: Tree, path: str, *, start: int | None = None, end: int | None = None, limit: int = 100, filter: Callable[[dict], bool] | None = None) -> list[dict]`: requires the leaf at `path` to have a `Log` state (raises `ToolError` otherwise). Caps `limit` at 1000 (raise `ValueError` above).
- All four return JSON-serializable plain dicts/lists ready for harness wrapping.
- Tests per tool: contract, bounded outputs, error-as-data, edge cases (empty tree, missing path, log on a Table-state node).

**Accept:** Each tool has at least 4 tests covering happy + bounds + error path + missing.

**Test:** `uv run pytest tests/unit/test_tools.py -v`

---

### [P5-2] [seq] [ ] P1: Tool re-exports + property tests for bounds

**Files:** `src/pmstate/__init__.py`, `tests/unit/test_tools_bounds.py`

**Instructions:**
- Re-export `list_tree`, `get_state`, `find_state`, `read_log`, `ToolError`.
- Hypothesis: `read_log(limit=N)` never returns more than `N` rows for any tree shape and any N in `[1, 1000]`.
- Hypothesis: `find_state(max_results=K)` never returns more than `K` matches.
- Hypothesis: `list_tree(depth=D)` for `D ∈ [1, 3]` never returns rows from depth > D.

**Accept:** Three property tests pass; bounds invariants hold.

**Test:** `uv run pytest tests/unit/test_tools_bounds.py -v --hypothesis-show-statistics`

---

# Phase 6: Claude Agent SDK harness + filesystem watcher

**Plan ref:** § "Phase 6"

### [P6-1] [seq] [ ] P1: Filesystem watcher integration

**Files:** `src/pmstate/_watcher.py`, `tests/unit/test_watcher.py`

**Instructions:**
- Internal `_watcher.py`: `def watch(root: Path, on_change: Callable[[set[Path]], None], *, force_polling: bool | None = None) -> threading.Thread`.
- Auto-detects WSL2 `/mnt/c/...` paths and sets `force_polling=True` if not explicitly overridden (per envelope research § 4).
- Uses `watchfiles.watch` (sync) inside the thread; calls `on_change` with the set of changed file paths on each event.
- Returns the thread (daemon=True) so harness can manage lifecycle.
- Tests: simulate file changes in `tmp_path`, assert callback fires within 3 seconds; WSL detection is correct (mock `os.path.realpath`).

**Accept:** Watcher fires callback on `tmp_path` writes; WSL detection toggles polling correctly.

**Test:** `uv run pytest tests/unit/test_watcher.py -v`

---

### [P6-2] [seq] [ ] P1: Claude Agent SDK harness adapter

**Files:** `src/pmstate/adapters/__init__.py`, `src/pmstate/adapters/claude_sdk.py`, `tests/integration/test_harness_smoke.py`

**Instructions:**
- `Harness(tree: Tree, *, root_dir: Path, model: str = "claude-sonnet-4-6", system: str | None = None, watch: bool = True)`. Frozen attrs class.
- `.run(prompt: str | None = None) -> str | None`: builds the system prompt — concatenates `load_agents_md(root_dir)` (if present) + the four-tool descriptions + `system` override. Registers tools wrapping `list_tree`/`get_state`/`find_state`/`read_log` for the SDK. If `prompt` is `None`, runs interactively; else one-shot returns the agent's final string.
- Watcher: when `watch=True`, spawn `_watcher.watch(root_dir, ...)` that calls `rollup.invalidate_path(...)` on each change. The agent picks up fresh state on its next `get_state` call.
- Smoke test: instantiate `Harness` with a fake LLM (mock the SDK's invocation point), assert AGENTS.md was added to system prompt, assert all four tools are registered, assert one-shot prompt returns a value.
- This is an integration-level test; mark with `@pytest.mark.integration` so it can be filtered.

**Accept:** Smoke test passes with fake LLM; AGENTS.md content is in the system prompt; all four tools registered.

**Test:** `uv run pytest tests/integration/test_harness_smoke.py -v -m integration`

---

### [P6-3] [seq] [ ] P1: Harness re-exports + claude-sdk extra

**Files:** `src/pmstate/__init__.py`, `pyproject.toml`

**Instructions:**
- Re-export `Harness as ClaudeHarness` from `pmstate.adapters.claude_sdk` (clear naming so future adapters get sibling names).
- Confirm `[project.optional-dependencies]` `claude-sdk = ["claude-agent-sdk>=...]` is wired so `pip install pmstate[claude-sdk]` pulls the SDK.
- Add `__all__` entry.

**Accept:** `from pmstate import ClaudeHarness` works after `pip install pmstate[claude-sdk]`; raises clear `ImportError` if extra not installed.

**Test:** `uv run pytest tests/unit/test_public_api.py -v` (extended)

---

# Phase 7: Procurement integration + v0.1 release

**Plan ref:** § "Phase 7"

### [P7-1] [seq] [ ] P1: Procurement example tree, views, reducers

**Files:** `examples/procurement/tree.py`, `examples/procurement/views.py`, `examples/procurement/reducers.py`, `examples/procurement/AGENTS.md`

**Instructions:**
- Implement the 28-LOC procurement example from `_devdocs/research/2026-05-06-pmstate-external-validation.md` § 4. Verbatim API; minor rewriting OK if it preserves the LOC budget.
- `views.py`: `quote_view`, `lpo_view` with the contract from the plan.
- `reducers.py`: `procurement_rollup` returning `{open_quotes, open_lpos, blocked}`.
- `tree.py`: builds `procurement` Node with the three children, returns a `Tree`.
- `AGENTS.md`: 30–60 lines describing the procurement domain to the agent — vendor terminology, what "blocked" means (>5 pending quotes), expected event types.
- Combined LOC: `wc -l examples/procurement/{tree,views,reducers}.py` ≤ 50.

**Accept:** Combined LOC ≤ 50; tree constructs without errors; AGENTS.md renders.

**Test:** `wc -l examples/procurement/{tree,views,reducers}.py | tail -1` ≤ 50; `uv run python -c "from examples.procurement.tree import build_tree; t = build_tree(); print(t.get('/procurement'))"`

---

### [P7-2] [parallel-after:P7-1] [ ] P1: Synthetic seed data generator

**Files:** `examples/procurement/seed_data.py`

**Instructions:**
- Generates ~50 events into `examples/procurement/state/quotes.jsonl`, `lpos.jsonl`, and a `vendors.json` Table.
- Reproducible: fixed RNG seed (`random.Random(42)`).
- Event types: `pmstate.quote.received`, `pmstate.quote.approved`, `pmstate.quote.withdrawn`, `pmstate.lpo.issued`. Realistic-ish distribution: ~30 quotes, ~15 approvals, ~3 withdrawals, ~10 LPOs.
- Run as `python -m examples.procurement.seed_data`; idempotent (deletes existing state files first).

**Accept:** Running the script produces deterministic JSONL files of the right shape; `read_events` can read them.

**Test:** `uv run python -m examples.procurement.seed_data && uv run python -c "from pmstate import read_events; print(sum(1 for _ in read_events('examples/procurement/state/quotes.jsonl')))"`

---

### [P7-3] [seq after P7-1] [ ] P1: Run script

**Files:** `examples/procurement/run.py`

**Instructions:**
- Glues `tree.py` + `seed_data` + `ClaudeHarness`. Reads a prompt from `sys.argv[1]` (one-shot mode), passes it through the harness, prints the response.
- Top-of-file docstring warns: "real-LLM run, costs money. Set ANTHROPIC_API_KEY."
- README's quickstart points to this file.

**Accept:** `python examples/procurement/run.py "what's pending in procurement?"` runs end-to-end against a real Claude session and prints a coherent answer (manual verification by Mats).

**Test:** Manual run by Mats with `ANTHROPIC_API_KEY` set.

---

### [P7-4] [parallel-after:P7-1] [ ] P1: End-to-end integration test (fake LLM)

**Files:** `tests/integration/test_procurement_e2e.py`

**Instructions:**
- Use a fake LLM (mock `claude-agent-sdk`'s invocation) that exercises all four tools deterministically.
- Build the tree, seed data, run a fake-prompt session.
- Assert: each of the four tools was called at least once; final rolled-up procurement view matches expected `{open_quotes, open_lpos, blocked}` from the deterministic seed data.

**Accept:** Test passes in CI without an API key; coverage includes all four tools.

**Test:** `uv run pytest tests/integration/test_procurement_e2e.py -v`

---

### [P7-5] [seq] [ ] P1: 0.1.0 release

**Files:** `src/pmstate/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md`

**Instructions:**
- Bump `__version__` to `"0.1.0"` in `src/pmstate/__init__.py` AND `version = "0.1.0"` in `pyproject.toml`.
- Create `CHANGELOG.md`: top entry `## 0.1.0 — 2026-MM-DD` with: "First release. Single user (Laterite). API unstable; breaking changes without warning. Procurement v0.1 runs end-to-end."
- Update README.md "Quickstart" section to point at `examples/procurement/run.py`.
- Add PyPI + CI badges to README header.
- Tag commit `v0.1.0`. Mats publishes via `uv build && uv publish` (manual, same flow as P0-8).

**Accept:** `pip install pmstate==0.1.0` in a fresh venv works; version reported as `0.1.0`; README quickstart references the working example.

**Test:** Manual fresh-venv install + `python -c "import pmstate; assert pmstate.__version__ == '0.1.0'"`.

---

## Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| One real Laterite procurement process runs end-to-end | `examples/procurement/run.py "..."` returns coherent answer using all four tools (manual run, P7-3) |
| Procurement example LOC ≤ 50 | `wc -l examples/procurement/{tree,views,reducers}.py` ≤ 50 (P7-1) |
| Test coverage ≥ 80% | `uv run pytest --cov=pmstate --cov-fail-under=80` green in CI |
| `pmstate` reserved on PyPI | `pip install pmstate==0.0.1` works after P0-8; `==0.1.0` after P7-5 |
| Atomic JSONL appends | Hypothesis test in P2-5 passes |
| ULID + idempotency | Hypothesis test in P2-1 + P2-5 passes |
| All four tools work + AGENTS.md loaded | Smoke test in P6-2 passes |
| README is approachable | Manual: stranger can copy-paste quickstart and run procurement example in <5 min after `pip install pmstate[claude-sdk]` |
| Production-grade check applied per phase | Plan § "Code quality standard" 7-question checklist walked at each phase boundary |

---

## Tag-and-status conventions

- Update `[ ]` → `[x]` as tasks complete.
- Add `[blocked: reason]` if a task hits an external blocker.
- Per-phase: after the last task in a phase, run `uv run pytest -v --cov=pmstate --cov-fail-under=80` and `uv run ruff check . && uv run mypy src` before starting the next phase.

## Out of scope (recorded — see plan § "Explicit non-goals (v0.1)")

- LangGraph checkpointer adapter
- `summarize_branch(path)` agent tool
- Brokered transport for sub-second event reactivity
- `correlation_id` envelope field
- Concurrent writers per leaf
- Plugin system / second-user abstractions
- Stranger-facing docs site
- Community PR acceptance
- The Laterite implementation repo (separate, future plan)
