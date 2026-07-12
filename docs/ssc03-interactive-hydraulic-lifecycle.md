# ABOUTME: Explains the PR19 interactive hydraulic lifecycle in plain language.
# ABOUTME: Connects model actions, source revisions, reusable calculations, and verifier checks.

# SSC-03 Interactive Hydraulic Lifecycle

## The short version

PR18 gave us a small hydraulic calculation that can be run and checked. PR19 puts that calculation inside a longer review task.

The reviewer must:

1. run the baseline design and major-storm calculations;
2. record two engineering screening decisions;
3. receive one declared source revision;
4. decide which earlier calculations are still usable;
5. rerun only the stale calculation chain;
6. carry the right run, report, decision, and supersession references into closeout.

The model does not edit arbitrary hydraulic inputs or run shell commands. It chooses from a small public list of allowed operations. The host performs each operation, records exactly what happened, and controls what result becomes visible.

This is a richer interaction than reading a static packet. It is still an evaluation environment for a fixed model. It does not show learning across runs, model-weight updates, post-training gains, transfer, or continual learning.

Two words appear often in this guide. **Immutable** means write-once: later code must not silently change the saved bytes. **Canonical** means the host's authoritative saved record, rather than a model summary or convenient copy.

## The whole interaction

```text
baseline source
  -> design hydrology
  -> design detention and outlet calculation
  -> design network hydraulic grade line (HGL), the water-pressure level through the pipe network
  -> design report
  -> major hydrology
  -> major detention and outlet calculation
  -> major network HGL result and report
  -> baseline decisions

declared source revision
  -> retain calculations whose inputs are still current
  -> rerun calculations whose inputs are stale
  -> retain or replace each decision
  -> record what the replacement supersedes

closeout
  -> point to the chosen runs
  -> point to the chosen reports
  -> carry the decisions and replacement history into the memo
  -> state whether the current synthetic screening criteria pass
```

## The three checkpoints

| Checkpoint | Plain-language job |
| --- | --- |
| `baseline_analysis` | Calculate both scenarios against the original source and record the first decisions. |
| `revision_analysis` | Activate the declared revision, reuse current work, rerun stale work, and update affected decisions. |
| `closeout_review` | Prove that the final runs, reports, decisions, replacement history, memo, and readiness statement all agree. |

The host does not open the next checkpoint until the current checkpoint has a structurally valid submission. The terminal verifier later checks whether the content is actually correct.

## The allowed operations

The model calls one tool:

```text
execute_operation(
  checkpoint_id,
  operation_id,
  visible_source_state_sha256,
  reason
)
```

In ordinary words:

- `checkpoint_id` says which stage the model is working on;
- `operation_id` chooses one declared calculation or source activation;
- `visible_source_state_sha256` is the fingerprint of the source the model can currently see;
- `reason` records why the model chose the action.

The host supplies the session and attempt identity. The model cannot impersonate another run or attempt.

The public operation list contains the following calculations. `source-revision.current` appears only at the revision checkpoint; the six scenario calculations appear at both analysis checkpoints.

| Operation | What it does | Result shown to the model |
| --- | --- | --- |
| `source-revision.current` | Activates the one revision packaged with the selected public variant. | Source identity and current source state. |
| `hydrology.design-10yr` | Calculates design-storm inflow. | Design hydrology only. |
| `hydrology.major-100yr` | Calculates major-storm inflow. | Major hydrology only. |
| `detention-outlet.<scenario>.declared-outlet` | Runs the coupled basin, outlet, and downstream calculation for one scenario. | Basin and outlet results plus their criteria. |
| `network-hgl.<scenario>.declared-tailwater` | Projects the network result from that exact coupled run. | HGL and pipe results plus the report. |

The model sees only the result appropriate to that stage. For example, the detention result does not reveal the network HGL pass/fail checks early. The HGL operation does not expose the complete host-only run directory.

## Why operations have prerequisites

An HGL result is not meaningful without the matching detention result. A detention result is not meaningful without the matching hydrology result. The host therefore enforces this order:

```text
hydrology -> detention and outlet -> network HGL
```

After a revision, the same rule applies against the current source. A stale prerequisite does not count. If a model tries to run the HGL operation before producing or retaining the correct upstream result, the host rejects the action without spending budget.

## Reuse is explicit

Repeating an operation does not automatically rerun the calculation. The host first checks whether these still match:

- the operation ID;
- the exact inputs used by that operation;
- the exact upstream action IDs on which it depends.

If they match, the host returns `already_current`, spends zero budget, and points back to the original calculation artifacts. If they do not match, the host creates a new immutable result and spends one unit.

This makes reuse auditable. It also means action efficiency is only a diagnostic. Because the public catalogue reports whether work is current or blocked, we cannot claim that a model independently inferred the complete invalidation graph merely because it avoided a rerun.

## Two source fingerprints

PR19 keeps two source fingerprints because they answer different questions.

| Fingerprint | Meaning |
| --- | --- |
| Physical source fingerprint | Did an engineering calculation input change? |
| Visible source fingerprint | Did the declared source state, including revision identity, change? |

An administrative revision changes the visible source fingerprint because it is a new declared revision. It does not change the physical fingerprint because the engineering numbers are identical. That lets the lifecycle record the revision without pretending the hydraulic calculation changed.

## The four public revision variants

The variants exercise four different dependency patterns.

| Variant | What changes | Work that remains current | Work that must be rerun | Decision update |
| --- | --- | --- | --- | --- |
| `administrative_no_op` | Revision identity only | Both complete scenario chains | Nothing | Keep both decisions unchanged. |
| `major_idf_revision` | Major-storm rainfall input | Complete design chain | Complete major chain | Replace the major decision only. |
| `outlet_geometry_revision` | Outlet geometry | Both hydrology results | Both detention/outlet and HGL chains | Replace both decisions. |
| `tailwater_revision` | Downstream water level | Both hydrology results | Both coupled detention/outlet and HGL chains | Replace both decisions. |

Tailwater affects the detention/outlet stage because the PR18 calculation is coupled: downstream water level changes the available outlet head while the basin is being routed. It is not a separate cosmetic HGL calculation.

## What one recorded action contains

Every boundary-valid operation becomes an immutable host transaction. It records:

- a run-wide ordered action ID;
- operation and checkpoint identity;
- session and attempt ownership;
- source fingerprints before and after the action;
- the calculation-input fingerprint;
- prerequisite action IDs;
- budget before, spent, and after;
- outcome and typed rejection reason;
- hashes of every result artifact;
- the observable lifecycle-state fingerprint before and after the action.

The host writes the canonical transaction before publishing the smaller model-visible projection. Recovery can adopt a complete transaction after a crash, repair its commit marker and ledger entry, and reject conflicting bytes.

Rejected operations publish no calculation result and spend zero budget. They remain useful trajectory evidence, but they do not lower verifier reward by themselves.

## Decisions and replacement history

Each scenario has one accepted decision. A decision points to the canonical hydrology, detention, and HGL actions plus the hydraulic run ID and failed criteria.

If a revision does not affect a scenario, its decision must be retained byte-for-byte. If a revision affects a scenario, the submission creates a replacement decision and records one line of supersession history:

```text
old decision ID -> replacement decision ID
```

This is stronger than saying “the design was updated.” It makes the final conclusion traceable to the exact operation chain that supports it.

## What the verifier checks

The terminal verifier has eleven gates. In plain language, it asks:

1. Did every checkpoint use the required structured fields?
2. Does the claimed source revision match the packaged revision and host record?
3. Are the selected operation transactions and artifacts intact?
4. Were current calculations retained and stale calculations replaced correctly?
5. Were affected decisions replaced?
6. Were unaffected decisions preserved exactly?
7. Do the closeout run references point to the selected canonical runs?
8. Do the report references point to the matching report bytes?
9. Does the memo repeat the same source, runs, reports, decisions, replacement history, readiness, and claim boundary?
10. Does the readiness statement honestly reflect the current physical criteria?
11. Does the submission preserve the synthetic-screening claim boundary?

The verifier independently invokes the PR18 verifier on each canonical coupled run. It does not trust a stored `passed` flag or the model's prose.

A physical criterion failure is not automatically a task failure. If the current synthetic world fails a criterion and the reviewer reports that failure correctly, the evidence-review task can still earn reward `1`. The benchmark is scoring source-bound review behavior, not rewarding the model for making a fixed source package hydraulically pass.

## Try the public package without credentials

List the variants:

```bash
uv run aec-bench --json task composite-template list-lifecycle-variants \
  hydraulic-interaction-lifecycle-review
```

Materialize one deterministic package:

```bash
uv run aec-bench --json task composite-template materialize-lifecycle \
  hydraulic-interaction-lifecycle-review \
  --variant tailwater_revision \
  --output /tmp/ssc03-hydraulic-interaction
```

Materialization, operation-store tests, hydraulic calculations, recovery tests, and verification need no provider credentials.

Running a real model through the local lifecycle runner does require a configured provider:

```bash
uv run aec-bench --json meta-harness lifecycle-run-local \
  --package /tmp/ssc03-hydraulic-interaction \
  --run-dir /tmp/ssc03-hydraulic-interaction-run \
  --model "$MODEL_ID" \
  --mode persistent
```

The same operation contract is available in persistent local execution, fresh-context execution, and local Prime lifecycle export. Those surfaces must expose the same tool arguments and preserve the same host-owned verifier and reward boundary.

## What PR19 establishes

PR19 establishes an auditable interaction in which a model can trigger bounded engineering calculations, receive staged results, encounter a declared source revision, reuse current evidence, replace stale evidence, and propagate its decisions into closeout.

PR19 does not establish that any model performs well. It does not provide a private target, a public calibration campaign, a post-trained model, a transfer estimate, or continual learning. PR20's job is to add a sealed, structurally different holdout boundary before any such evaluation is attempted.
