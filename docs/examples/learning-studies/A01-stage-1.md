# A01 Stage 1: Artifact structural-transfer plumbing proof

| Field | Value |
| --- | --- |
| Class | Research |
| Status | Research |

This example records the deterministic, non-claim-bearing Release A integration
study. It uses real task loading, isolated artifact workspaces, task verifiers,
normal `TrialRecord` values, study recording, and matched assessment. A focused
adapter-boundary test double replaces only the paid model call.

## Frozen task relation

- Acquisition: `mechanical/heat-load/single-room-office-L3/brisbane-office-85m2`
- Probe: `mechanical/heat-load/single-room-office-L3/sydney-classroom-120m2`
- Family: `families/heat-load-single-room.toml`
- Relation: `brisbane-office-to-sydney-classroom`
- Primary projection: `heat-load-verifier-reward`

The authored invariant is the sequence of AS 1668.2 lookup, occupancy and
outside-air calculation, sensible and latent component calculation, and final
summation. The room program, standards row, climate, floor area, and internal
loads change. The target verifier scores the same twelve named quantities with
target-specific values, so copied acquisition numbers do not pass.

This relation still needs mechanical-engineering domain review and benchmark
review before a claim-bearing campaign.

## Stage 1 arms

```text
cold-reset
  Sydney classroom probe -> discard candidate learner state

structured-memory
  Brisbane office acquisition
  -> release named public evaluation
  -> consolidate one bounded method artifact
  -> Sydney classroom probe
  -> discard candidate learner state
```

Both arms use the same fixed synthetic adapter and model identifiers. The cold
and exposed probe are the same exact task and repetition. The model test double
returns an incorrect probe result without the committed method artifact and a
correct result when that artifact is present. This behaviour tests wiring; it is
not evidence that a model learned.

## Observed deterministic result

The end-to-end test asserts these task-owned verifier rewards:

| Experience | Reward |
| --- | ---: |
| Cold Sydney probe | 0.0 |
| Brisbane acquisition | 1.0 |
| Exposed Sydney probe | 1.0 |

The one matched pair has a normalised exposed-minus-cold effect of `+1.0`.
Assessment reports `descriptive_only`, because the family relation has not yet
received the required human domain and benchmark reviews. The result therefore
proves the comparison and downgrade paths, not structural transfer by a model.

The test also proves that verifier files and family metadata are absent from
actor-visible execution, only released public feedback enters learner state,
probe candidates are deleted, and a completed resume does not rerun a trial.

## Domain-review questions

1. Does the change from office to classroom retain one governing method, or is
   the different AS 1668.2 row a material applicability change?
2. Do the shared wording and twelve-field output shape make the probe too close
   at the surface level?
3. Does the Sydney task have enough cold headroom for a real-model pilot?
4. Is canonical verifier reward sufficiently informative, or does the task
   owner need a named calculation-correctness projection?
