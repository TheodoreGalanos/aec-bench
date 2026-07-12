# ABOUTME: Explains the explicit external-provider boundary for sealed lifecycle holdouts.
# ABOUTME: Separates private full-fidelity task evidence from public registries and export surfaces.

# SSC-03 Sealed Holdout Boundary

## The short version

PR20 adds a way to run one already-selected private lifecycle without teaching the public repository how to find it.

The private provider supplies three things: a package builder, an operation resolver, and a task verifier. The host binds that provider to one exact package path for one execution context. It does not add the provider or its target to the public template or lifecycle registries.

```text
out-of-tree provider -> sealed package -> explicit host mount -> ordinary lifecycle tools
                                                |
                                                +-> host invokes task verifier

sealed package -X-> public registry / Prime export / public experiment record
```

The provider is task authority, not execution authority. It can produce evidence and define the verifier, but it never enters the model tool schema, returns reward through the environment, or owns checkpoint/session identity. The host still invokes and validates the terminal verifier.

## What is public

The public repository contains only:

- the versioned `SealedLifecycleProvider` protocol;
- the package-scoped `SealedLifecycleMount`;
- a generic host-written receipt;
- stable redacted failure codes;
- a domain-neutral fake provider under `tests/support/`.

There is no provider discovery, entry-point scan, environment-variable lookup, target list, or private module import.

The generic receipt contains exactly:

```json
{
  "provider_protocol_sha256": "<public protocol hash>",
  "public_export": "forbidden",
  "public_registry": "forbidden",
  "schema_version": "1",
  "visibility": "holdout"
}
```

It contains no target ID, provider path, prompt, source filename, operation ID, expected answer, verifier name, gate ID, or free-form annotation.

## What stays private

The selected target's identity, instructions, source packet, action mapping, expected calculations, verifier rules, and provider source remain outside this repository. Its full package, run, ledger, submissions, operation artifacts, and verifier result remain inside the explicitly chosen private roots.

That distinction matters because experiment manifests and `TrialRecord`s are intentionally full-fidelity audit artifacts. They include prompts, file inventories, hashes, verifier identity, and paths. PR20 therefore rejects a sealed package before the normal public experiment-record or `TrialRecord` path can copy that material. It does not pretend those records are redacted.

PR22 adds a separate private recorder without relaxing either public guard. The target freeze commits to one canonical private audit root before public results exist. That root fixes the authority, execution, and ledger paths; changing any of them is rejected before adapter work. The local claim is therefore exclusive within that trusted filesystem namespace. Preventing the filesystem owner from deleting or restoring the whole namespace would require external write-once storage or a transparency service.

A complete private record is explicitly `holdout`, lives under the target-bound owner-only ledger root, and snapshots every regular package and run file plus exactly four authority files: the public calibration freeze, private target freeze, one-shot claim, and private audit manifest. The audit manifest binds the selected condition, runtime and interaction identities, normalized session evidence, verifier result, code provenance, and exact package/run inventories. The claimed clean repository must have the same source inventory as the loaded `aec_bench` package; an unrelated clean checkout cannot lend the run false provenance.

The run-start authorization hash is written into lifecycle state and the first durable ledger event before adapter execution. Recovery requires both bindings, so a run created before the claim cannot be made valid by adding marker files afterward. A persistent- or fresh-context crash with durable attempt lineage and trajectory but no `agent_result.json` is sealed as an interrupted, zero-reward partial record without calling the adapter again.

Validation checks every recorded artifact hash and rejects extra or missing snapshot files. It rebinds the snapshotted package to the explicitly supplied provider in a temporary directory, replays the resolver history, and reruns deterministic task verification there. Replay therefore cannot mutate the immutable snapshot and cannot fall back to public provider discovery.

The sealed PR16 evaluator accepts exactly one private target record and an explicit matching mount. It checks the selected condition and public calibration references against the snapshotted calibration freeze, validates and replays the private record, and reports only descriptive holdout generalization. The public receipt builder invokes this evaluator itself; it does not accept a caller-constructed passing summary.

## How a private run is mounted

The external caller already holds one provider instance for one selected target:

```python
provider = PrivateLifecycleProvider(...)
mount = materialize_sealed_lifecycle(provider, private_package_dir)

with mount.activate():
    # Use the ordinary lifecycle workspace and control tools.
    # Host verification also happens inside this context.
    result = verify_lifecycle_template(private_package_dir, private_run_dir)
```

The mount is bound to the package's canonical path, regular-file content hash, and file-and-directory tree hash. A copied package does not inherit the mount. Adding an empty directory or otherwise changing the package invalidates it. A later process must explicitly reconstruct the provider and call `bind_sealed_lifecycle(...)`; mounts are not discovered or serialized automatically.

Provider exceptions are replaced at the boundary with stable codes such as `sealed_provider_resolver_failed` or `sealed_provider_verifier_failed`. This prevents a private path, target label, or rule from becoming a model-facing tool error or public command error.

## Public surfaces fail closed

| Surface | Sealed-package behavior |
| --- | --- |
| Public template and lifecycle listings | Provider is absent; listing never calls it |
| Public variant metadata | Returns no public variant |
| Public lifecycle verification without the exact mount | Rejected |
| Local Prime lifecycle export | Rejected before reading the initial instruction |
| Normal experiment manifest and `TrialRecord` finalization | Rejected before writing output |
| Dedicated private holdout finalization | Requires the exact mount, target-bound private layout, freezes, claim, run authorization, selected condition, and owner-only roots |
| Public aggregate receipt | Reruns the sealed evaluator from the real record and explicit mount; caller summaries are rejected |
| Public calibration planner | Cannot enumerate or select the provider |

The receipt check takes precedence even if someone places it on a package that otherwise resembles a registered public variant. This closes a subtle export risk: public variant validation alone does not make every instruction byte safe to publish.

## Actual execution proof

PR20 was exercised with an out-of-tree synthetic pump-station provider, not the committed fake fixture and not pytest. The private task used a three-checkpoint graph covering source review, duty analysis, and a final selection note. Four operations produced a pump curve, system curve, duty point, and power/NPSH check with exact prerequisite lineage.

The production workspace and control tools completed all three checkpoints and all four operations. The host invoked and validated the provider-supplied task verifier; all five gates passed and it returned reward `1.0`. The public lifecycle registry was unchanged, the sealed template was absent from it, and both unmounted execution and unmounted verification were rejected before writing an unmounted run.

Only that aggregate proof is recorded here. The target ID, source values, prompts, operation map, expected results, verifier implementation, and full artifacts are not committed.

## What PR20 does not prove

PR20 provides no model-performance result, public calibration result, holdout generalization estimate, post-training result, learner transfer, or continual learning. The execution proof used deterministic host calls and no provider credentials.

It also does not make the synthetic pump values engineering-authoritative. Pump curves, wet-well behavior, rising-main assumptions, operating rules, tolerances, and NPSH treatment still require engineering review before a private target is frozen.

PR21 adds the preregistered public-only selector and write-once condition freeze, including runtime, operation-protocol, and tool-schema identity. Its deterministic campaign proof is not model evidence; the paid public run still requires an approved model and spend envelope. PR22 now has the target commitment, target-bound local claim, pre-execution run authorization, one-shot execution and recovery orchestration, sealed PR16 evaluator, internally derived aggregate receipt, recorder seam, and access-controlled full-fidelity record contract.

No actual holdout result can be reported yet. The public calibration campaign has not run, no selected condition has been frozen from real campaign records, and no real private target has consumed its committed slot. The implemented result contract remains descriptive holdout generalization, not causal transfer, learning across runs, or continual learning.
