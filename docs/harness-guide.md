# ABOUTME: Guide for the Python harness domain covering orchestration, execution, isolation, and provider abstraction.
# ABOUTME: Defines Harbor-backed execution integration, output collection, and the trial lifecycle.

# Harness Guide

The harness orchestrates trials. It resolves experiment configuration, provisions environments, executes agents, runs verifiers, and records TrialRecords. In the current Python direction, Harbor is the preferred execution substrate and Python owns the typed orchestration boundary around it.

Parent document: [ARCHITECTURE.md](ARCHITECTURE.md).
Data shapes: [CONTRACTS.md](CONTRACTS.md).
Rules: [INVARIANTS.md](INVARIANTS.md).

---

## What the Harness Does

The harness owns the trial lifecycle:

1. select task and agent pairs,
2. provision environment,
3. execute agent,
4. collect outputs,
5. run verifier,
6. record TrialRecord,
7. clean up.

Failures at any step are recorded, not hidden.

## Execution Substrate Strategy

The harness boundary remains part of the Python architecture, but the default implementation path should not duplicate Harbor's proven execution stack.

Preferred split:

- Harbor owns task staging, image build, sandbox/container lifecycle, agent invocation, and verifier invocation.
- Python owns validated manifests, task selection, TrialRecord construction, transcript normalization, evaluation ingestion, and downstream reporting.

That keeps vendor-facing execution logic behind a narrow boundary while preserving the domain invariants in Python.

---

## Job Configuration

Python job configuration remains declarative. It should bind:

- task selection,
- agent configuration,
- compute target,
- experiment metadata.

Every substantial experiment should have a corresponding smoke config using the same adapter and compute target on a representative subset.

---

## Compute Abstraction

Every compute boundary must provide the equivalent of:

- environment build or selection,
- launch,
- monitoring,
- output retrieval,
- resource enforcement,
- teardown.

For the immediate Python path, those capabilities should be satisfied by Harbor wherever possible rather than reimplemented directly. Domain logic should not know whether execution ultimately lands on local Docker, remote Docker, Modal, Morph Cloud, or a future backend.

Direct Python compute backends may exist for parity checks and focused smoke runs, but vendor-specific transport code belongs outside `harness/`. For example, the direct Morph Cloud runner keeps trial orchestration in `harness/` while SDK calls, file transfer, Docker host setup, and snapshot cleanup live under `providers/`.

### Morph Cloud Through Harbor

Morph Cloud support is additive to the earlier direct provider spike. It does not immediately supersede that work.

The normal `aec-bench run --backend morph` path should go through Harbor. Python emits a Harbor environment config with an import path of `aec_bench.providers.morph_harbor:MorphHarborEnvironment`; Harbor still owns task staging, agent invocation, artifact collection, and verifier invocation. The Morph adapter only translates Harbor's `BaseEnvironment` calls into Morph Cloud operations.

The direct `MorphSandboxRunner` remains useful for provider-level smoke tests, direct evolution execution, and backend parity checks. It should not become the main experiment CLI route unless Harbor cannot express the workflow.

Morph-specific SDK calls and remote Docker host handling belong under `providers/`. The harness may select `morph`, validate the contract, and ingest results, but it should not import the Morph SDK directly.

---

## Isolation

Each trial runs in a fresh isolated environment with:

- clean filesystem,
- isolated processes,
- declared network policy,
- enforced resource limits.

Ephemeral containers are a feature, not an inconvenience. They force important state through explicit collection paths.

---

## Input Staging

Before execution:

1. resolve manifest,
2. fetch files,
3. verify hashes,
4. place tools,
5. confirm workspace completeness.

If Harbor is the execution substrate, Python should verify the staging contract at the boundary and ingest the resulting artefacts, not restage the same task independently.

---

## Output Collection and Verification

The harness collects:

- agent output,
- transcript,
- adapter metadata,
- timing,
- token usage where available,
- verifier reward,
- verifier details where available.

Collection happens before teardown and still runs on failures.

Verification remains separate from evaluation:

- verifier: task-specific mechanical scoring,
- evaluation: cross-task enrichment and analysis.

---

## Scheduling and Idempotency

Trials are independent and can be scheduled concurrently within host-safe bounds.

The harness should support:

- failure isolation,
- progress tracking,
- resumable experiments,
- append-only reruns with new `trial_id` values.

Early implementation should validate these guarantees through Harbor first, then add direct Python backend parity checks only if required.
