# ABOUTME: Defines the current provenance categories and review rules for persisted and public AEC-Bench fields.
# ABOUTME: Keeps exact-byte integrity, authority evidence, commitments, versions, and event time within their owners.

# Provenance Policy

| Field | Value |
| --- | --- |
| Class | Normative |
| Status | Current |
| Owner | Contracts and benchmark governance |

## Purpose

This policy controls new and changed provenance-shaped fields in AEC-Bench. It
applies to persisted contracts, public schemas, evidence records, manifests,
and independently consumed protocols. It does not make provenance a new
runtime subsystem or transfer facts away from their domain owners.

The governing rule is:

> Git identifies repository source. Exact retained bytes use an integrity
> digest at their storage or trust boundary. Stable IDs identify domain
> entities and lineage. An authority owns evidence for the facts it controls.
> A named commitment protects a declared semantic or operational payload.
> Versions belong to independently evolving envelopes and independently
> distributed runtimes. Time records a real event.

The benchmark guarantees in [Benchmark invariants](INVARIANTS.md) remain the
higher authority. Current protected shapes and owners remain in
[Contracts](CONTRACTS.md) and [Architecture](ARCHITECTURE.md). This policy
classifies provenance fields and controls how contributors add them.

## Current scope

The guardrail classifies fields while owning formats complete their
migrations. A field in the legacy baseline is known migration debt. Its
presence in that baseline is not approval of its design.

This policy does not state that later provenance work is complete. In
particular:

- ordinary Kernel, Harness, execution-program, evaluation, stage, and
  run-bundle contracts are plain immutable models with stable references;
- current content-reference contracts use `ContentAddressedModel` only when
  the digest is part of the current contract; ordinary records use strict
  domain fields;
- `ArtifactRef` is the universal exact-byte store reference, including for
  current trial inputs, outputs, authority evidence, provider evidence, and
  typed extensions;
- the dataset and trial owners use schema 2 with exact source and artifact
  references; an evaluation regime uses one schema-1 envelope and one
  `ArtifactRef` as its compatibility identity; run-bundle contracts keep their
  supported shapes until their owning changes are implemented;
- `RunManifest` owns shared run identity and `TrialRecord` keeps
  execution, evaluation, and evidence status separate;
- current DeepSeek evidence v3, retained evidence v2, qualification v2,
  retained qualification v1, and installed World actor protocols remain
  supported.

New code must not copy a legacy pattern only because the baseline contains it.

Registration is not proof that every current consumer verifies a claim. The
registry records known gaps without inventing checks that do not exist. These
gaps currently include remaining extension-level `ArtifactReference`
consumers and the lack of a production reader for the actor and World transport
JSONL evidence. A temporary exception must name its scope and removal
milestone. Later owning changes must close the check or remove the field.

## Provenance categories

Each registered field has exactly one primary category. A value can support
more than one use, but one authority and one primary assertion must remain
clear.

### A. Source identity

Source identity states which repository-managed source or configuration was
used.

Use a full immutable Git commit at a run, release, generated-package,
qualification, or independently deployed component boundary. Record it once
at that boundary. A package version can remain beside a source revision when
the two values prove different facts.

For clean Git-managed source, do not add a second source-tree or per-file hash
for the same claim. Dirty source needs reconstructive bytes, such as a complete
snapshot or a patch with its base revision. An opaque dirty-tree digest is not
enough to reconstruct the source.

Current DeepSeek evidence uses `ProviderAdapterIdentity.source_revision` or a
reconstructive `source_snapshot`. The retained v2 reader keeps
`aec_bench_revision` for its protected wire shape.

### B. Artifact integrity

Artifact integrity proves the exact bytes retained across a storage, process,
publication, or trust boundary.

The storage or evidence owner calculates the digest. The reader verifies it
against the retained bytes and fails closed on a mismatch. A digest does not
become the domain ID merely because the bytes can be serialized.

Current fail-closed examples include:

- `ArtifactRef.sha256`, which `ArtifactRepository` checks with the
  digest-derived artifact ID and retained byte size on every read;
- each DeepSeek evidence-v3 `ArtifactRef`, which is checked against the
  retained file bytes and size;
- `ImmutableArtifact.sha256`, which the immutable byte store checks on read;
  and
- the installed World actor client digest, which protects its deterministic
  installed byte tree.

`ArtifactReference.sha256` is a protected current field and a registered
temporary exception. Its current generic readers do not yet recalculate the
retained bytes at every read boundary. Do not use this gap as a pattern for new
artifact fields.

An embedded child value does not need an independent digest unless it is
stored, retrieved, authenticated, shared, or retained independently.

### C. Domain identity and lineage

Domain identity names a benchmark entity or a meaningful relationship.

Examples include `dataset_id`, `task_id`, `world_id`, `lifecycle_id`, `run_id`,
`trial_id`, `candidate_id`, `parent_candidate_id`, `seed`, and
`instance_index`. Use these IDs for domain references and lineage. Do not use a
content digest as a substitute.

Provider route, Harbor configuration, record format, local path, and transport
metadata do not enter task or World semantic identity when they do not change
task meaning. Git parentage does not replace explicit candidate lineage.

### D. Schema and protocol compatibility

Compatibility fields allow an independent producer and consumer to select a
reader, migrate data, or reject unsupported input.

Current valid examples include:

- `aec-bench/world-actor/1`;
- `aec-bench/actor-invocation/1`;
- `aec-bench/actor-invocation-evidence/1`;
- public library catalogue schema 2;
- `aec-bench/native-world-tool-surface/1`;
- `aec-bench/deepseek-evidence/3`, with a retained v2 reader; and
- `aec-bench/deepseek-qualification/2`, with a retained v1 reader.

A registered version must identify its independent reader behavior. Do not add
`schema_version` to an internal component only for symmetry. The current
`trajectory.jsonl` contract has no generic version header and does not gain one
through this policy.

### E. Domain event time

Event time records when a real event occurred.

Examples include `started_at`, `admitted_at`, `dispatched_at`, `observed_at`,
`completed_at`, `closed_at`, `published_at`, `reviewed_at`, `verified_at`, and a
qualification date. DeepSeek evidence `generated_at` records the evidence
emission event and is valid.

Time is not deterministic content identity. A catalogue-build time, listing
time, or current migration time must not be presented as the time of a
historical or semantic event.

### F. Semantic commitments

A semantic commitment binds a canonical declared surface. It does not need to
identify an independently stored artifact.

Current examples are the actor catalogue commitment and the public native-tool
surface commitment. They prove different facts:

- `catalogue_sha256` binds the frozen authority-owned action catalogue; and
- `public_tool_surface_sha256` binds the exact tool declaration shown to the
  model.

The registry must name the payload, canonicalization, owner, consumer, and
failure behavior. A consumer must reject or mark incompatible a value that
does not match. Do not rename an unexplained self-hash to `commitment`.

### G. Operational commitments

An operational commitment supports idempotency, conflict detection, privacy,
retry, recovery, ordering, or unknown-outcome reconciliation within one
authority.

`ActorInvocationAuthority` owns the current actor request fingerprint. Its
canonical payload includes the actor principal, opaque decision, action name,
arguments, and actor-invocation semantics. Provider request IDs, sessions,
tool-call IDs, transport, local paths, time, and retry counters do not enter
that logical identity.

The actor evidence JSONL also uses named decision, observation, result, error,
and task-receipt commitments. These can protect a claim without copying a
sensitive raw payload into the authority log. The evidence must not describe
the absent raw bytes as full reconstruction evidence.

Generic non-World native-tool replay remains owned by `ToolGatewayEndpoint`.
Its provider-scoped request derivation is not the World actor request identity
and must not be rejected by a broad fingerprint rule.

### H. Qualification and runtime attestation

Qualification and runtime attestation state what was declared, what was
resolved, what the model could see, and under which exact versions and provider
route a capability was proved.

Current DeepSeek evidence keeps these facts separate where applicable:

- AEC-Bench package version and source revision or source snapshot;
- SDK distribution and reported versions;
- runtime distribution and reported versions;
- plugin artifact and package-lock integrity;
- declared, resolved-runtime, and model-visible evidence levels;
- provider route and feature cell;
- qualification status and date; and
- retained qualification evidence.

Do not infer one evidence level from another. A local or keyless protocol test
does not prove a live provider route. Missing live evidence remains partial or
unqualified. See the current DeepSeek evidence and qualification contract in
[Contracts](CONTRACTS.md#provider-request-and-result-envelopes).

## Authority-owned evidence

Each authority owns evidence for the facts it controls. A different subsystem
can reference that evidence. It must not create a second authority for the
same fact.

| Authority | Evidence it owns | Evidence it does not own |
| --- | --- | --- |
| World | Causal state, domain actions and receipts, domain replay, and World evaluation evidence | Provider transport and SDK qualification |
| Lifecycle | Lifecycle state, events, close, and lifecycle evidence | World causal state |
| `ActorInvocationAuthority` | Logical request identity, admission, exact retry, conflicts, order, budget, terminal state, semantic evidence, and close | World transitions, host controls, verification, and reward |
| Provider adapter | Provider composition, correlation, transport evidence, model-visible declarations, and runtime attestation | Task truth, World replay, lifecycle truth, and evaluation truth |
| Experimentation | Qualification matrices, studies, governance, and promotion decisions | Provider runtime execution |
| Evaluation | Evaluation policy, critic outcomes, validity, and acceptance | Actor invocation replay |
| Ledger or artifact store | Exact retained bytes, immutable publication, and digest verification | Domain meaning |
| Trial record | Current references, timing, statuses, and outcome fields defined by its contract | A copied replacement for authority-owned state |

The exact current World and actor boundaries are defined in the
[Interactive-World Runtime](protocols/interactive-world-runtime.md). Provider
adapters remain transport and composition owners under
[Architecture](ARCHITECTURE.md#provider-integrations).

## Invocation replay and World replay

The word `replay` has two current meanings.

### Invocation replay

`ActorInvocationAuthority` answers operational questions:

- Has this logical request ID already been admitted?
- Is the repeated payload identical or conflicting?
- Is an earlier result available?
- Is the outcome unknown and awaiting reconciliation?
- Does the request violate order, budget, or terminal state?

The same request ID and canonical payload can return the retained outcome. The
same request ID with a different payload is a conflict. Provider correlation
does not change either decision.

### World replay

The World owner answers causal questions:

- Which task-owned transition occurred?
- Which state and observation resulted?
- Can the episode be reconstructed?
- Which task receipt was produced?
- How does the World evaluate the episode?

Invocation evidence can refer to a World receipt. It does not replace the
World repository or causal record. Prime and DeepSeek can use different
transports while sharing one trial-wide actor authority.

## Semantic identity and exact evidence identity

Semantic identity contains the domain meaning that can change the benchmark
outcome. Exact evidence identity covers the complete bytes retained at an
evidence boundary.

Changing provider route, compression, record encoding, local socket path, or
package layout can change evidence bytes without changing task semantics.
Changing a task instruction, World action schema, verifier rule, or
outcome-affecting parameter changes semantic identity.

Do not force both claims into one hash. Use domain IDs for semantic entities,
named commitments for declared surfaces, and byte digests for retained
artifacts.

## Digest and artifact-reference rules

A retained digest is valid only when it makes one of these claims:

1. It verifies exact retained bytes.
2. It is a named semantic commitment.
3. It is a named operational commitment.
4. It supports an exact qualification or runtime-attestation claim.

For every digest, the registry must state:

- the exact payload;
- the canonicalization and algorithm;
- the owning authority;
- the consumer and validation behavior;
- the mismatch behavior;
- the retention scope; and
- why Git, a parent artifact, a stable domain ID, or existing authority evidence
  is not sufficient.

Acceptable uses include immutable-store verification, detached-package
integrity, actor catalogue and public-surface commitments, request conflict
detection, hidden acceptance commitments, plugin and package-lock evidence,
and provider evidence-manifest binding.

Unacceptable uses include:

- a generic `content_sha256` on an ordinary internal model;
- a digest used as the ID of a domain entity;
- a raw artifact digest beside a reference that already authenticates the same
  bytes;
- a clean Git revision plus another tree digest for the same source claim;
- parent and embedded-child self-hashes for the same retained representation;
- a provider request ID in logical World request identity;
- provider or transport fields in task-profile identity;
- a deterministic definition that contains the time it was serialized; and
- a generic `content_hash` used without a named payload or consumer.

New independently retained artifacts use `ArtifactRef`. The protected
`ArtifactReference` and owner-specific evidence references remain in their
current contracts until their owners deliberately migrate them. Do not add a
second reference for bytes that already have one authoritative reference.

## Version and timestamp rules

A version is valid when an independent producer or reader changes behavior by
that version. Valid uses include a package distribution, external protocol,
persisted schema with migration or rejection behavior, and qualification
matrix. A generic change-history version on an internal value is not valid.

A timestamp or date must name its event. A listing command must use the
historical event time or omit the field. It must not create a new time for an
old event. Event time does not enter task, dataset, actor request, or tool
surface identity unless the event itself is the domain fact being represented.

## Duplication rules

One fact has one authoritative representation. The scanner and review must
flag:

- a raw digest beside an artifact reference for the same bytes;
- clean source revision and source-tree digest for the same source boundary;
- a parent digest copied into embedded children;
- provider correlation used in logical request identity;
- a semantic commitment stored as a generic self-hash; and
- a deterministic definition with generation time.

Retained DeepSeek evidence v2 repeats path and SHA-256 values in some
claim-specific references and in its artifact table. Its reader still checks
that both declarations agree. New evidence v3 uses complete `ArtifactRef`
values as authenticated table keys and verifies every reference against the
table and retained bytes.

## Registry and scanner

[`provenance-registry.toml`](../provenance-registry.toml) records approved
current fields and temporary exceptions. Each entry identifies its category,
owner, authority, payload, canonicalization, consumer, validation behavior,
mismatch behavior, retention, exposure, and rationale. Manifest fields use
logical protocol symbols because current actor and native-surface evidence is
written through dictionary and JSONL keys rather than only through model
fields.

[`scripts/check_provenance_fields.py`](../scripts/check_provenance_fields.py)
uses the Python AST. It inspects persisted or public fields declared through
Pydantic models, dataclasses, typed dictionaries, computed serializers,
manifest-building code, and Python Web schemas. It also identifies inherited
`ContentAddressedModel.content_sha256` fields as explicit content-reference
fields.

Run:

```bash
python scripts/check_provenance_fields.py --format text
python scripts/check_provenance_fields.py --format json
```

The scanner does not execute source modules. It does not treat ordinary local
variables or non-persisted cryptographic operations as fields.

The AST can prove field shape and some high-confidence structural rules. It
cannot prove that a runtime consumer verifies bytes, that a protocol test
proves live provider behavior, or that a dynamically constructed key is
complete. Focused behavior tests and contract review remain required. The
current scanner also does not replace later vocabulary checks for non-Python
client schemas or generated OpenAPI.

## Legacy baseline and temporary exceptions

[`provenance-baseline.json`](../provenance-baseline.json) contains current
unregistered legacy symbols. It is separate from the registry so that legacy
presence cannot become an allowlist.

The baseline follows these rules:

- it can shrink when a legacy field is removed or registered with a valid
  current claim;
- it cannot grow in a pull request;
- a renamed field counts as a new field;
- a deleted field must also leave the baseline;
- a new unregistered field fails; and
- reports show legacy fields as unclassified instead of inventing an owner or
  category.

A temporary exception belongs in the registry, not the legacy baseline. It
must identify the duplicated or exceptional claim, explain why the current
trust model needs it, and name a removal milestone or successor decision.

## Migration rules

Changes that later migrate a protected or persisted form follow these rules:

- new writers emit the selected canonical form;
- readers accept only the documented legacy forms during the stated
  transition window;
- invalid authoritative evidence is rejected or quarantined;
- migration does not invent a missing payload to preserve an old hash;
- DeepSeek evidence v2, qualification v1, Prime lifecycle schema 2, and World
  actor protocols remain readable through their explicit retained readers;
- golden fixtures state whether each old form migrates, remains read-only, is
  corrupt, or is unsupported; and
- the current contract, architecture, or protocol document changes in the same
  pull request as the implemented boundary.

The baseline entry leaves only when the corresponding implementation and
fixtures have changed. Documentation alone does not complete a migration.

## Contributor review

Before adding or changing a provenance-shaped field, answer:

1. What exact fact does the field assert?
2. Which authority owns that fact?
3. Which provenance category applies?
4. What canonical payload and algorithm are used?
5. Which code consumes and validates the value?
6. What happens when the value disagrees with the source or payload?
7. How long is the value retained?
8. Why are Git, a parent artifact, a stable domain ID, or existing authority
   evidence not sufficient?
9. Can the value change when benchmark semantics have not changed?
10. Does it reveal or copy sensitive, provider, private, or holdout content?

The pull-request declaration is:

```text
Does this change add a hash, commitment, fingerprint, version,
revision, timestamp, artifact reference, or attestation?

If yes:
- Which provenance category applies?
- Which authority owns it?
- What canonical payload is covered?
- What consumes and validates it?
- What happens on mismatch?
```

If these questions do not have concrete answers, the field is provenance
noise and must not be added.
