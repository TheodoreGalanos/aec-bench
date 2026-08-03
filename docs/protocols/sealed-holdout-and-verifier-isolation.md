# ABOUTME: Defines the current sealed lifecycle provider, one-shot holdout audit, and public disclosure boundary.
# ABOUTME: Separates private target and verifier authority from public commitments and aggregate results.

# Sealed Holdout and Verifier Isolation

| Field | Value |
| --- | --- |
| Class | Protocol |
| Status | Current |

This protocol applies to sealed evidence-lifecycle holdout targets. It protects
target identity, task content, verifier authority, execution evidence, and the
private trial record while still producing a publicly checkable commitment and
a deliberately small aggregate result.

It does not claim that a local filesystem provides external, permanent
tamper-proof custody. Stronger claims require an independent write-once store,
transparency service, or equivalent external authority.

## Boundary and ownership

The host owns target selection, execution, reward interpretation, persistence,
and public disclosure. A `SealedLifecycleProvider` supplies one already-selected
target through four operations: materialize, validate, build an operation
resolver, and verify.

The provider is package scoped:

- it has no discovery or enumeration operation;
- it is mounted only for one exact canonical package path and call context;
- its task identity must not collide with a public template registration;
- the host records both the package identity hash and the complete package-tree
  hash, then rejects later drift;
- provider exceptions become stable, non-disclosing host error codes.

The generic `sealed-lifecycle.json` receipt contains only the provider protocol
hash, schema version, holdout visibility, and prohibitions on public registry
and export use. It contains no target identifier, package path, provider name,
or verifier detail.

## Frozen authority and one-shot execution

One audit follows this order:

1. Public calibration fixes the selected execution condition and campaign
   identities.
2. The private target freeze binds that calibration, the exact target package
   and tree hashes, opaque provider/resolver/verifier contract hashes, one
   canonical private root, and exactly one holdout repetition.
3. The public target commitment discloses only salted commitment and public
   campaign identities. It states that target selection occurred before public
   results.
4. The private claim is created with exclusive publication. An existing claim
   consumes the one execution slot.
5. The run-start marker binds the claim, both freezes, selected condition,
   Python version, execution directory, and private ledger. Its hash is the
   first durable run authorization event.
6. The host runs the selected fresh- or persistent-context condition with the
   sealed mount active.
7. The private finalizer snapshots the package, run, authority files,
   repository provenance, agent evidence, and verifier result into an
   owner-only ledger.

Private roots and authority files must be canonical, non-symlinked, and
owner-only. The repository provenance captured at finalization must come from a
clean Git checkout.

Recovery can finalize artifacts already bound by the run-start marker. It does
not accept another adapter or rerun model work. If execution was interrupted,
recovery records the incomplete result instead of converting it into success.

## Private record and replay

The normal public lifecycle finalizer and Prime exporter reject sealed
packages. Sealed runs use the private finalizer, which binds the exact mounted
package, frozen public condition, run authorization, canonical session
evidence, verifier result, and copied artifacts.

Validation rebuilds the private `TrialRecord` from its immutable snapshot and
replays through an explicitly rebound sealed provider mount. The ordinary
public transfer evaluator refuses to treat an unmounted sealed target as
evidence. The sealed evaluator accepts exactly one target and verifies that its
public calibration references and selected condition match the frozen
authority.

A verified reward of zero is valid holdout evidence. Missing authority,
inconsistent provenance, invalid snapshots, or an unavailable sealed mount
make the target not evaluable; they do not become a zero reward or a successful
trial.

## Public disclosure

The public surface has two artifacts:

- an opaque pre-execution target commitment bound to the public experiment,
  manifest, and plan;
- a post-execution aggregate receipt recomputed through the real sealed
  evaluator.

The aggregate receipt is an exact allow-list: calibration freeze hash, target
commitment hash, descriptive interpretation, explicit exclusions of causal and
cross-run-learning claims, target and eligible counts, mean reward when one is
defined, and closed pass/fail/not-evaluable counts. It does not copy private
record, package, target, session, verifier, or artifact fields.

## Failure semantics

The boundary fails closed when:

- a provider contract, materialization, validation, resolver, or verifier call
  is invalid;
- a package mutates, uses a symlink or special entry, or collides with the
  public registry;
- a freeze, claim, marker, selected condition, repository, session record, or
  verifier result does not match the frozen authority;
- private paths are non-canonical, overlap source material, or are not
  owner-only;
- a second claim or conflicting write attempts to replace write-once evidence;
- a public exporter, recorder, or evaluator receives sealed private material.

## Implementation and proof

- Provider and mount: [`provider.py`](../../src/aec_bench/task_world_templates/lifecycles/provider.py)
- Freeze, commitment, claim, and receipt: [`evidence_lifecycle_holdout_audit.py`](../../src/aec_bench/meta_harness/evidence_lifecycle_holdout_audit.py)
- One-shot execution and recovery: [`evidence_lifecycle_holdout_execution.py`](../../src/aec_bench/meta_harness/evidence_lifecycle_holdout_execution.py)
- Private record and replay validation: [`evidence_lifecycle_holdout_record.py`](../../src/aec_bench/meta_harness/evidence_lifecycle_holdout_record.py)
- Sealed transfer evaluation: [`evidence_lifecycle_transfer.py`](../../src/aec_bench/meta_harness/evidence_lifecycle_transfer.py)
- Provider boundary tests: [`test_sealed_lifecycle_provider.py`](../../tests/task_world_templates/test_sealed_lifecycle_provider.py)
- Audit contract tests: [`test_evidence_lifecycle_holdout_audit_contracts.py`](../../tests/meta_harness/test_evidence_lifecycle_holdout_audit_contracts.py)
- Execution and recovery tests: [`test_evidence_lifecycle_holdout_execution.py`](../../tests/meta_harness/test_evidence_lifecycle_holdout_execution.py)
- Private record tests: [`test_evidence_lifecycle_holdout_record.py`](../../tests/meta_harness/test_evidence_lifecycle_holdout_record.py)
- Sealed evaluation tests: [`test_evidence_lifecycle_sealed_transfer.py`](../../tests/meta_harness/test_evidence_lifecycle_sealed_transfer.py)
