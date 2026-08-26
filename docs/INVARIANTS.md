# ABOUTME: Defines stable benchmark-validity and reproducibility guarantees for AEC-Bench.
# ABOUTME: Keeps implementation-specific storage, transport, and migration procedures in owned protocols.

# Benchmark Invariants

| Field | Value |
| --- | --- |
| Class | Normative |
| Status | Normative |

These guarantees survive changes to package layout, storage engine, provider,
class design, and transport. Detailed enforcement belongs in the protocol that
owns a boundary.

## Objective order

Resolve conflicts in this order:

```text
validity > reproducibility > coverage > cost > throughput
```

Convenience, speed, and coverage do not justify evidence that misstates agent
capability.

## Benchmark validity

A reported result must measure the declared task, agent condition, execution
limits, and verifier. A run is invalid when contamination, identity drift,
missing evidence, or an execution failure prevents that claim.

Validation cannot be weakened, bypassed, or replaced with a fake-success path
to keep a workflow moving.

## Reproducible identity and provenance

Every outcome-affecting input and implementation identity must be explicit and
recorded. Depending on the execution family, this includes task and verifier
revision, agent and model identity, prompts, tools, provider configuration,
limits, runtime dependencies, generated inputs, seeds, and referenced
artifacts.

A record may use content-addressed references to durable artifacts. It does not
need to embed every byte. Ordinary implementation details that cannot change
the benchmark outcome do not become provenance merely for completeness.

## Actor-visible information is controlled

An actor receives only the observation, files, tools, and history allowed by
the task's visibility policy. Hidden verifier state, gold answers, holdout
content, host controls, sibling rollout information, and future conditions do
not enter actor-visible observations or provider requests.

Outcome-affecting host state must still be explicit in host-owned evidence. No
benchmark result may depend on an undocumented environment default, mutable
local alias, or unrecorded provider setting.

## Task semantics are provider-neutral

Tasks and task worlds define instructions, state, actions, events,
observations, and verifier meaning without depending on a model vendor,
provider SDK, compute backend, or Harbor transport.

Adapters and provider integrations translate execution protocols. They do not
branch on task type, rewrite task intent, apply task transitions, or score
outputs. Interactive-world ownership is detailed in the
[current runtime protocol](protocols/interactive-world-runtime.md).

## Evaluation owns scoring and invalidity

Evaluation owns reward, validity interpretation, score breakdowns, behavioural
analysis, error taxonomy, and confidence. A task verifier supplies task-owned
evidence; communication and presentation surfaces report the established
result.

A report, dashboard, provider adapter, or persistence layer must not invent a
second metric definition or repair an invalid result into a valid one.

## Candidate evidence is exact

Any score, descriptor, gate decision, archive outcome, graveyard entry, or
lineage update that names a candidate MUST derive from evidence produced by
that exact candidate. Candidate identity MUST remain distinct from trial and
attempt identity. Parent and child evidence MUST remain separate, and a
comparison MUST use the same ordered evaluation cases for both candidates.

`TrialRecord` remains the evidence authority. Evolution-owned assessments,
archive entries, graveyard projections, and swarm decisions may summarise that
evidence, but they MUST NOT invent a score, descriptor, validity result, or
candidate snapshot. A rejected or invalid candidate MUST NOT become an
accepted archive or global-best candidate through an event, placeholder, or
agent-owned score.

## Public and holdout material remain separate

Visibility is explicit. Public catalogues, examples, training exports,
calibration, reports, and generated documentation must not contain sealed or
holdout task content.

Missing visibility is unknown, not public. Holdout-derived evidence can change
general principles only through a deliberate review that does not reveal the
held-out target.

## Failures remain failures

Provider errors, timeouts, interrupted sessions, malformed output, missing
artifacts, verifier failures, identity mismatches, and incomplete recovery must
remain explicit. They do not silently become successful trials, zero-cost
successes, or evidence for the requested condition.

When an external effect might have occurred but cannot be confirmed, record an
unknown or incomplete outcome and reconcile durable evidence before retrying.

## Human judgment is structured and attributable

Expert judgment that affects a benchmark result must identify the reviewer or
review authority, decision, time, applicable evidence, and provenance. Free
text can explain a decision but is not the only authoritative record.

Calibration, adjudication, and confidence claims must state the evidence and
method that support them.

## Maintained code has a permanent owner

Every file needed to build, run, generate, verify, certify, migrate, or test the
product must live in a tracked repository surface with an explicit owner.
Ignored research, generated output, temporary worktrees, and delivery-phase
folders are not production dependencies.

How rarely a command runs does not make it research. A required generator,
certifier, or recovery command is maintained code.

## Deterministic worlds replay

A deterministic task world must reproduce its recorded transitions and final
state exactly, or within a numerical tolerance declared by the task before the
run. Replay uses the recorded task, profile, implementation, inputs, action
order, and state lineage rather than current defaults.

Non-determinism must be explicit, bounded, and represented in the evaluation
claim. A replay mismatch invalidates claims that depend on deterministic
reconstruction.

## Boundary data is validated before use

Untrusted, external, persisted, and cross-process data must be validated at the
boundary that admits it. Strict internal contracts reject undeclared fields;
external ingestion may accept upstream additions only where the boundary is
deliberately lenient.

Do not create a boundary model for a local intermediate value solely for
uniformity. The [contract index](CONTRACTS.md) identifies the major protected
families.

## Published evidence has declared integrity semantics

Accepted trial evidence, benchmark datasets, published manifests, and other
named content-addressed artifacts preserve the immutability or append-only
semantics their contract declares. Source code, internal APIs, tests,
configuration, and in-memory state are replaceable implementation.

Detailed checkpoint, recovery, and publication rules belong to
[Staged evidence and publication](protocols/staged-evidence-and-publication.md),
not in this invariant set.
