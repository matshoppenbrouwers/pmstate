# Spec authoring smoke transcript (recorded)

**Recorded:** 2026-05-07
**Inputs:** `docs/spec-authoring.md` + the user prompt
*"build me a tracker for my Q3 hiring pipeline"*

The orchestrating agent (Claude Code) is expected to produce the YAML
below. The companion file `tests/integration/spec_authoring_sample.yaml`
is the verbatim output and is fed through `_spec.parse_spec` in
`tests/integration/test_cli_e2e.py` to confirm the schema accepts it.

---

## Recorded reply

```yaml
name: hiring-pipeline-q3
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
        - {name: rejected,   state: table}
events:
  candidate.added:
    schema: {name: str, source: str}
  candidate.advanced:
    schema: {from: str, to: str, note: str}
  candidate.rejected:
    schema: {reason: str}
```

The agent followed the 5-rule recipe verbatim:

1. Buckets: leads, screened, interviews, offers, hires, rejected.
2. Streams (`log`) for the funnel stages; snapshot (`table`) for rejected.
3. Event names in `subject.verb-past-tense` form.
4. `pipeline_rollup` reducer because the user said "tracker" (implies
   aggregate health of the funnel).
5. `pmstate_version: "0.2.0"` to match the installed CLI.
