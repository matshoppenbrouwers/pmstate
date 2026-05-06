# Event envelope — external research

**Date:** 2026-05-06
**Scope:** Validate / refine the v0.1 event envelope for pmstate against external standards. Pmstate is a tiny library (one user, filesystem substrate, single writer per leaf, human-speed processes). Recommendations are sized to that.
**Inputs:** Internal design doc — `2026-05-06-pmstate-internal-design.md`, Q4.

---

## 1. TL;DR

- **CloudEvents:** adopt the *attribute names* (`id`, `source`, `type`, `specversion`, `time`, `subject`, `dataschema`) and the JSON structured-mode shape. Skip the SDK; hand-roll a 30-line dataclass. Cost is near-zero, gain is interop and a stable vocabulary that survives if pmstate ever speaks to anything else.
- **ID:** **ULID**, via [`python-ulid`](https://pypi.org/project/python-ulid/) (mdomke). UUIDv7 is the more "correct" 2026 pick if you live in a UUID world; we don't, and ULID's Crockford-base32 string is shorter, grep-friendlier, and already in our envelope.
- **Watcher:** **`watchfiles`** (Rust-backed, maintained by samuelcolvin). Default to its event API; force `force_polling=True` when the path lives on a Windows-mounted `/mnt/c/...` drive under WSL2 — inotify does not fire there.
- **Atomicity:** trust `O_APPEND` for JSONL rows **strictly under 4096 bytes on local Linux/ext4 only**. macOS APFS has known `O_APPEND` interleaving bugs; NFS has none of these guarantees. Since v0.1 is single-writer-per-leaf, atomicity-against-readers is the only thing that matters and `O_APPEND` + `fsync` covers it. Use rename-and-replace only for the mutable `Table(path)` files.
- **Causation vs correlation:** keep `causation_id` (cheap, useful for tracing rollup invalidation chains). Do **not** add `correlation_id` for v0.1 — pmstate has no cross-leaf "logical flow" concept yet. Reserve the field name; add it the day a real consumer asks for it.

---

## 2. CloudEvents fit analysis

**The spec.** CloudEvents v1.0.2 is a CNCF-graduated standard. JSON structured-mode places all attributes as top-level JSON properties; extension attributes sit alongside core attributes (no nesting). Required attributes: `id`, `source` (URI-reference), `specversion` (`"1.0"`), `type` ([CNCF spec](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md)). Optional standard attributes: `subject`, `time` (RFC 3339), `datacontenttype`, `dataschema`. Payload goes in `data` (or `data_base64` for binary) per the [JSON format](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/formats/json-format.md).

**Field-by-field map:**

| pmstate v0.1 | CloudEvents | Notes |
|---|---|---|
| `id: ULID` | `id` (string) | Direct. CE only requires `(source, id)` uniqueness. ULIDs are globally unique; we satisfy trivially. |
| `type: string` | `type` (reverse-DNS recommended) | Rename our types to `state.updated` → `tech.pmstate.state.updated` *if* we ever publish externally. For internal v0.1, short names are fine; CE allows any string. |
| `source: path` | `source` (URI-reference) | A filesystem path *is* a valid URI-reference (`/active/fieldwork/enum_log`). Compliant. |
| `version: int` | **extension** `dataschemaversion` or use `dataschema` (URI) | CE has no `version` field for the event type. Two options: (a) put schema version in `type` (`state.updated.v2`), Greg-Young-style; (b) extension attribute. Recommend **(a)** — keeps the envelope flat and consumers branch on `type` anyway. |
| `timestamp: ISO8601` | `time` (RFC 3339) | Direct rename. RFC 3339 is a subset of ISO 8601; same string works. |
| `payload: {...}` | `data` (any JSON) | Direct rename. |
| `causation_id?: ULID` | **extension** `causationid` | CE extension naming rule: lowercase alphanum, no underscores. Becomes `causationid`. |
| — | `subject` (optional) | Free win. Use this for the leaf-relative path or the entity ID inside the payload (e.g., quote ID). Lets generic CE tooling filter without parsing `data`. |

**What we'd inherit.** The Python SDK ([`cloudevents` on PyPI](https://github.com/cloudevents/sdk-python)) gives us structured/binary HTTP marshallers, Kafka headers, Pydantic models. **None of that helps v0.1** — we write JSONL rows and read JSONL rows. The SDK adds a dependency for serialization we already have (`json.dumps`).

**Recommendation: adopt the shape, skip the SDK.** Use CloudEvents attribute names (`id`, `source`, `type`, `time`, `subject`, `data`, `specversion`, `causationid`) so a future consumer can read our JSONL with `from cloudevents.http import from_dict` for free. Drop our `version` field and bake the version into `type` instead — this is what the CE community does in practice and it sidesteps the "two versions of the same event type" ambiguity. Total adoption cost: one rename pass.

**Don't adopt:** the SDK, binary mode, the HTTP / Kafka transports. Pmstate's transport is the file. CE is a wire-format borrow, not a runtime dependency.

---

## 3. ULID vs UUIDv7

Both are time-sortable, both encode a 48-bit ms timestamp + randomness ([Authgear comparison](https://www.authgear.com/post/time-sortable-identifiers-uuidv7-ulid-snowflake), [Honeybadger](https://www.honeybadger.io/blog/uuids-and-ulids/)).

| Dimension | ULID | UUIDv7 (RFC 9562, 2024) |
|---|---|---|
| String length | 26 chars (Crockford base32) | 36 chars (hex + dashes) |
| Bytes | 16 | 16 |
| Stdlib | No (third-party) | Yes — [`uuid.uuid7()`](https://docs.python.org/3/library/uuid.html) added in **Python 3.14** (Oct 2025); pmstate targets ≥3.11 |
| Sortability | String-sortable | String-sortable |
| Monotonicity within ms | Spec defines a monotonic mode | RFC 9562 allows but doesn't mandate |
| URL/grep friendliness | Better (no dashes, all-caps base32) | Worse |
| Database ecosystem | Weaker | Strong (Postgres, MySQL native types) |

**Recommendation: ULID, with [`python-ulid`](https://github.com/mdomke/python-ulid) (mdomke).** Maintained, monotonic by default, supports microsecond precision via an extension mode, last release 2025-08. Reasons:

1. The envelope already specifies ULID. Switching to UUIDv7 would force a string format change in our log files that we'd see every `ls`.
2. Pmstate has zero database story. The "UUIDs are native in Postgres" advantage doesn't apply.
3. ULID's 26-char shape is tangibly nicer when grepping JSONL logs, which is how pmstate users will debug.
4. We don't need cross-machine clock sync — single writer per leaf means each leaf's ULIDs are issued by one process and remain ordered. Even with clock skew across machines, **per-node** ordering (req 2) is preserved because each node has one writer.

If `python-ulid` ever goes unmaintained, the migration to `uuid.uuid7()` is mechanical: change `id` generator, accept that old rows have shorter IDs forever. Cheap escape hatch.

**Avoid:** `ulid-py` / `py-ulid` (older, less maintained forks per PyPI), `ahawker/ulid` (more featureful but heavier dep).

---

## 4. Filesystem watcher pick

**Pick: [`watchfiles`](https://github.com/samuelcolvin/watchfiles).** Rust-backed (uses [`notify`](https://github.com/notify-rs/notify) under the hood), tiny API, async + sync support, actively maintained, used by uvicorn's reloader. On Linux it uses inotify, on macOS FSEvents, on Windows ReadDirectoryChangesW — same coverage as `watchdog` ([PyPI](https://pypi.org/project/watchdog/)) but faster and with a smaller surface.

**WSL2 caveat (load-bearing for this project, given the dev environment):** inotify does **not fire** for changes made by Windows processes on a `/mnt/c/...` mount ([WSL issue #4739](https://github.com/microsoft/WSL/issues/4739)). Pmstate state files written from a Windows-side editor or sync tool will be invisible to a WSL-side watcher. Mitigation: pass `force_polling=True` (configurable in watchfiles) when the watched path starts with `/mnt/`. Default to event-driven elsewhere.

**Fallbacks:**
- `watchdog` if a pure-Python dep is needed for some packaging reason. Same platform coverage, slower, larger ecosystem.
- For Linux-only deployments, `inotify_simple` is fine but adds platform-specific code paths we don't need.

**Pitfalls regardless of library:**
- Editor "atomic save" rewrites a file via rename → watchers see `delete` + `create`, not `modify`. Pmstate writers should use `O_APPEND` for logs (no rename involved) and `os.replace()` for `Table` files (one rename event).
- Polling at sub-second rates is fine for human-speed processes (req: surveys over days). Default poll interval 100 ms is wasteful; pmstate should default to 1–2 s when polling.

---

## 5. Atomicity caveats

**The POSIX guarantee.** `write(2)` calls of `<= PIPE_BUF` bytes to a file opened `O_APPEND` are atomic with respect to other writers ([POSIX `write`](https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html)). On Linux `PIPE_BUF == 4096`. This is what makes `tail -f /var/log/syslog` work without seeing torn lines.

**What this means for pmstate:**

| Filesystem | Atomic O_APPEND for ≤4096 B? | Recommendation |
|---|---|---|
| Linux ext4, xfs, btrfs (local) | Yes | Trust it. JSONL rows must stay under 4 KiB. |
| Linux tmpfs | Yes | Same. |
| macOS APFS | **No** — known to interleave concurrent appends ([Apple Bug 37859698, see notthewizard.com](https://www.notthewizard.com/2014/06/17/are-files-appends-really-atomic/)) | Single-writer per leaf masks this; v0.1 is safe. Document it. |
| WSL2 over ext4 (in-WSL filesystem) | Yes | Trust. |
| WSL2 over `/mnt/c/...` (DrvFs/9P) | **Unspecified, treat as no** | Discourage state files on Windows-mounted paths; if unavoidable, use a write-then-rename pattern. |
| NFS / SMB / cloud FS | **No** | Out of scope for v0.1; document as "not supported". |

**Implication for the writer API.** Pmstate v0.1 is single-writer-per-leaf. The atomicity question reduces from "do writers tear each other?" (irrelevant — there's one) to "can a reader see a half-written line?". `O_APPEND` + a single `write()` of `serialized_event + "\n"` answers no on the platforms we care about (Linux local, WSL2 in-WSL, macOS in single-writer mode). For `Table(path)` mutable files, use `os.replace()` (POSIX `rename`) on a temp file in the same directory — atomic on every POSIX filesystem.

**Concrete writer contract:**

```python
def append_event(log_path: Path, event: dict) -> None:
    line = json.dumps(event, separators=(",", ":")) + "\n"
    if len(line.encode("utf-8")) > 4000:  # 96-byte safety margin
        raise EventTooLargeError(len(line))
    with open(log_path, "ab") as f:  # ab = O_APPEND in CPython on POSIX
        f.write(line.encode("utf-8"))
        # fsync optional; trades durability for throughput
```

The 4000-byte ceiling is a real constraint authors must know about. Documented as: "events with payloads > 3 KiB should reference an external file via `subject` rather than inline."

---

## 6. Schema evolution stance

**Pattern: additive-only minor changes, version-bump-via-`type`-suffix on breaking, upcaster registry on read.**

This is the [Greg Young pattern](https://leanpub.com/esversioning/read) (free book), confirmed by [event-driven.io](https://event-driven.io/en/simple_events_versioning_patterns/) and [Marten's docs](https://martendb.io/events/versioning) as the cheapest workable approach.

**Three rules:**

1. **Additive-only fields.** New optional fields can be added to a payload without bumping anything. Consumers ignore unknown fields. No upcaster needed.
2. **Renames or semantic changes are a new event type.** `state.updated` becomes `state.updated.v2` (suffix in `type`). The old type continues to exist on disk forever. *Greg Young's rule: a new version must be convertible from the old; if not, it isn't a new version, it's a new event.*
3. **Upcaster registry on the reader side.** When consumers (rollups, agent tools) read a log, they pass each row through a registry keyed by `type`. If the type is current, no transform. If the type is an old version, the upcaster transforms it to the current shape before the consumer sees it. Old data on disk is never rewritten.

**Example shape:**

```python
UPCASTERS: dict[str, Callable[[dict], dict]] = {
    "state.updated": lambda e: {**e, "type": "state.updated.v2",
                                "data": {**e["data"], "actor": "unknown"}},
}

def read_events(path: Path) -> Iterator[dict]:
    with open(path) as f:
        for line in f:
            event = json.loads(line)
            while event["type"] in UPCASTERS:
                event = UPCASTERS[event["type"]](event)
            yield event
```

This keeps the storage format additive-only-forever, lets new code read 5-year-old logs, and means we never have to run a migration. Cost: a dict with as many entries as we have breaking changes (probably <10 over the framework's life).

**Don't:** SQL-style migrations that rewrite log files, JSON Schema validation as a hard gate (it fights the duck-typed view philosophy from Q5), or storing schemas separately. The schema *is* the consumer code.

---

## 7. Causation vs correlation

[Arkency's classic post](https://blog.arkency.com/correlation-id-and-causation-id-in-evented-systems/) and [Rails Event Store docs](https://railseventstore.org/docs/v2/correlation_causation/) frame this clearly:

- **`causation_id`** = "the event that directly caused this one." A B-caused-by-A pointer. Forms a tree.
- **`correlation_id`** = "the logical flow this event belongs to." Stable across the whole tree. Forms a flat group.

When event B is emitted in response to event A: `B.causation_id = A.id`, `B.correlation_id = A.correlation_id` (inherited). The root event sets `correlation_id = id`.

**For pmstate v0.1: keep `causation_id`, skip `correlation_id`.**

Why keep causation:
- Pmstate has a real causation tree. A leaf write fires `state.updated`, which causes a parent's `notify.parent`, which (in v0.2) might cause a rollup recompute event. Tracing "why did Active's view change?" is exactly this chain.
- Cost is one optional ULID field. Trivial.

Why skip correlation:
- Pmstate has no cross-leaf "logical flow" concept yet. The closest analog is "the user request that triggered this," and v0.1 has no user-request abstraction.
- Adding it now means inventing a definition we don't need. Better to add it the day a real consumer (e.g., a future audit tool) needs to ask "show me everything that happened because the user clicked Approve."
- The field name is reserved by convention; no one will trip over us adding it later.

**OpenTelemetry comparison.** OTel uses `trace_id` (≈ correlation) and `span_id` + `parent_span_id` (≈ causation tree) in its [log data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/). The semantics match, the names differ. If pmstate ever needs to interop with OTel-shaped tooling, the mapping is mechanical: `causation_id` ↔ `parent_span_id`-of-causing-span, `correlation_id` ↔ `trace_id`. We don't need to adopt OTel names — they're noisier and assume tracing infrastructure we don't have.

**On AsyncAPI 3.x.** [AsyncAPI](https://www.asyncapi.com/docs/reference/specification/v3.0.0) is a wire-contract-and-docs spec for message-driven APIs (Kafka, MQTT, AMQP). Pmstate has no broker, no producers other than itself, no consumers other than itself. AsyncAPI is **overkill** for v0.1. Revisit only if pmstate ever publishes events over a broker — then write a 50-line AsyncAPI document for the catalog and stop.

---

## 8. Concrete envelope v1.0

```jsonc
{
  "specversion": "1.0",                     // CloudEvents marker, fixed string
  "id": "01J9X8KQZP5M3T7VW2NXBQRGFA",        // ULID, required, globally unique
  "source": "/active/fieldwork/enum_log",   // pmstate node path, required
  "type": "pmstate.state.updated",          // dotted, version suffix on break
  "time": "2026-05-06T14:23:11.482Z",       // RFC 3339, required for pmstate
  "subject": "quote_id:Q-2026-0184",        // optional, payload-discriminator
  "datacontenttype": "application/json",    // optional, omit if redundant
  "data": { "field": "qty", "old": 100, "new": 120 },
  "causationid": "01J9X8KK7H6E2RD8YJF1NW5VBT" // optional, lowercase per CE ext rule
}
```

**Field reference:**

| Field | Type | Required | Source |
|---|---|---|---|
| `specversion` | `"1.0"` | Yes | CloudEvents required |
| `id` | string (ULID, 26 chars Crockford base32) | Yes | CloudEvents required |
| `source` | string (URI-ref, leading slash; pmstate node path) | Yes | CloudEvents required |
| `type` | string (dotted, lowercase, optional `.vN` suffix) | Yes | CloudEvents required |
| `time` | string (RFC 3339, UTC, ms precision) | Yes for pmstate (CE optional) | CloudEvents optional |
| `subject` | string (free-form discriminator) | No | CloudEvents optional |
| `datacontenttype` | string (default `application/json`, often omitted) | No | CloudEvents optional |
| `data` | object (type-specific payload) | Yes for non-marker events | CloudEvents standard |
| `causationid` | string (ULID; the event that caused this one) | No | pmstate extension |

**Constraints (writer-enforced):**

- Total serialized line (incl. trailing `\n`) ≤ 4000 bytes. Larger payloads must externalize via `subject`.
- `time` always UTC, always millisecond precision, always trailing `Z`.
- `type` follows `pmstate.<domain>.<verb>[.vN]`; absence of `.vN` means v1 implicitly.
- `id` is the writer's responsibility; readers MUST treat duplicate `id` as the same event (idempotency).

**Migration from current envelope:** rename `timestamp` → `time`, `causation_id` → `causationid`, drop `version` (fold into `type`), add `specversion`. Optionally add `subject`. Five-line patch in the writer; readers can be backward-compatible for one release via the upcaster pattern from §6.

**Not added (future work, when pulled by real need):**
- `correlation_id` — when cross-leaf flows become a thing.
- `dataschema` (URI to JSON Schema) — when external consumers want a schema.
- Binary mode / `data_base64` — when payloads carry non-JSON data.

---

## Sources

- CloudEvents spec v1.0.2: <https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md>
- CloudEvents JSON format: <https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/formats/json-format.md>
- CloudEvents Python SDK: <https://github.com/cloudevents/sdk-python>
- python-ulid: <https://github.com/mdomke/python-ulid>, <https://pypi.org/project/python-ulid/>
- UUIDv7 / RFC 9562: <https://datatracker.ietf.org/doc/rfc9562/>
- ULID/UUIDv7/Snowflake comparison: <https://www.authgear.com/post/time-sortable-identifiers-uuidv7-ulid-snowflake>
- Honeybadger UUID/ULID deep dive: <https://www.honeybadger.io/blog/uuids-and-ulids/>
- watchfiles: <https://github.com/samuelcolvin/watchfiles>
- watchdog: <https://pypi.org/project/watchdog/>
- WSL2 inotify limitation: <https://github.com/microsoft/WSL/issues/4739>
- watchfiles polling fallback feature request: <https://github.com/samuelcolvin/watchfiles/issues/134>
- POSIX write atomicity: <https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html>
- APFS atomic append issue: <https://www.notthewizard.com/2014/06/17/are-files-appends-really-atomic/>
- Greg Young, *Versioning in an Event Sourced System*: <https://leanpub.com/esversioning/read>
- Event versioning patterns (Oskar Dudycz): <https://event-driven.io/en/simple_events_versioning_patterns/>
- Marten event versioning: <https://martendb.io/events/versioning>
- Upcasting deep dive (Artium): <https://artium.ai/insights/event-sourcing-what-is-upcasting-a-deep-dive>
- Arkency: correlation and causation IDs: <https://blog.arkency.com/correlation-id-and-causation-id-in-evented-systems/>
- Rails Event Store, correlation/causation: <https://railseventstore.org/docs/v2/correlation_causation/>
- OpenTelemetry log data model: <https://opentelemetry.io/docs/specs/otel/logs/data-model/>
- OpenTelemetry semantic conventions for events: <https://opentelemetry.io/docs/specs/semconv/general/events/>
- AsyncAPI 3.0 spec: <https://www.asyncapi.com/docs/reference/specification/v3.0.0>
