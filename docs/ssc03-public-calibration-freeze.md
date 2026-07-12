# ABOUTME: Explains the preregistered public hydraulic campaign and frozen-condition contract.
# ABOUTME: Separates deterministic selection evidence from the later sealed holdout audit.

# SSC-03 Public Calibration and Condition Freeze

## The short version

PR21 turns the public PR19 hydraulic family into a campaign that can be run, compared, and frozen before anyone mounts the private PR20 target.

```text
preregistered public manifest
          |
          v
4 public variants x 4 context conditions x repetitions
          |
          v
immutable public TrialRecords
          |
          v
predeclared selector -> write-once frozen condition
                                  |
                                  +--X sealed holdout content
```

The selector makes no provider call, needs no provider credential, and accepts no target or sealed-package input. It does still resolve the public manifest's model-ID environment reference so it can prove that the requested manifest matches the campaign snapshot. It refuses to run while any sealed lifecycle mount is active.

## Why the campaign needed another execution seam

The earlier calibration runner assumed every task could provide a static `hidden/gold-submissions.json`. That works for the original staged document lifecycle. It is wrong for PR19: valid hydraulic submissions must name action IDs created by real prerequisite-bound operation transactions.

PR21 therefore registers a task-owned deterministic smoke environment for the public hydraulic lifecycle. The smoke driver executes the same source-bound hydrology, detention/outlet, HGL, source-revision, reuse, and recomputation operations that a model can request. It builds submissions from the resulting artifacts and action lineage, then lets the ordinary task verifier score the run. It does not invent static action IDs, bypass operations, call a model, or read verifier output while producing submissions.

Campaign inspection now smokes all four public variants successfully and expands the four execution/visibility conditions without writing the requested output or ledger roots. The smoke itself uses one credential-free in-process condition per variant; it does not pretend to execute a model under all four conditions.

## What is preregistered

The campaign manifest now optionally carries a strict `selection_policy`. A selectable campaign must declare all of the following before execution:

- selection objective: maximum mean task-verifier reward;
- coverage: the captured IDs of every currently registered public variant and every declared public repetition;
- treatment of incomplete candidates: ineligible;
- deterministic tie-break: canonical condition identity;
- required interaction protocol: lifecycle operations;
- public calibration repetitions;
- later holdout repetitions;
- a positive finite estimated per-trial cost and maximum estimated campaign spend.

The policy enters the manifest hash, expanded plan hash, and every planned trial ID. Each finalized `TrialRecord` snapshots the manifest and plan. Adding or changing the rule after seeing results therefore does not match the immutable campaign evidence.

Selectable execution must use the normal provider registry. The injectable registry seam remains available to legacy descriptive development runs, but it cannot mint evidence for a frozen model condition.

The cost values are planning guards, not provider-side billing limits. One repetition of the current design contains 16 trials but 40 potential provider sessions: one session for each persistent trial and three sessions for each fresh-context trial. At 60 turns per session, the configured ceiling is 2,400 turns. The estimate must be chosen conservatively for the selected model before execution.

## Which records may support selection

The freeze requires a record at the exact canonical ledger path for every planned trial. It loads the historical manifest and plan from the first immutable record, then rebuilds every record against that captured contract. Later planner or protocol source changes do not silently redefine the completed campaign. Record and referenced artifact bytes are read once, then the same bytes are parsed and hashed for the freeze.

A candidate condition is eligible only when all of its variant/repetition cells have:

- explicit `public` task visibility;
- a complete reproducible record from a clean Git source state;
- completed lifecycle execution and verifier invocation;
- stable requested and resolved model/adapter identity;
- exact realized runtime-provider dependency bytes;
- one stable lifecycle-operation protocol hash; and
- one stable model tool-schema hash.

A valid but incorrect model submission remains part of the mean reward. Schema or task failures are not silently discarded merely because they reduce a candidate's score. Provider failures, unresolved identities, partial records, missing cells, and protocol drift make the whole candidate ineligible.

The selector chooses the highest mean canonical verifier reward. Exact ties use the preregistered canonical condition identity, never an after-the-fact preference.

## What the freeze contains

The write-once JSON artifact binds:

- the public experiment, manifest, and plan hashes;
- every public `TrialRecord` path and content hash;
- every eligible and ineligible candidate plus reasons;
- requested and resolved model and adapter;
- runtime provider, distribution inventory, and realized dependency hash;
- execution mode and model-visible memory policy;
- per-session turn limit;
- lifecycle-operation protocol and complete tool-schema hashes;
- selected public mean reward; and
- the preregistered public and holdout repetition policy.

Publishing is atomic. Repeating the command with identical evidence is idempotent; different bytes at the same destination are rejected rather than replaced.

## Commands

Credential-free structural inspection:

```bash
SSC03_CALIBRATION_MODEL_ID=deterministic-plan \
uv run aec-bench --json meta-harness lifecycle-ablation \
  --config docs/examples/meta-harness/hydraulic-lifecycle-calibration.example.yaml \
  --dry-run
```

The placeholder above proves plan expansion, not the final model-bound trial identities. To inspect the exact campaign, set `SSC03_CALIBRATION_MODEL_ID` to the selected provider-routable model. Dry-run needs no provider credential. Before a paid run, replace the example cost estimate and load the selected provider configuration, then omit `--dry-run`. On a fresh campaign, provider-configuration preflight errors fail before the manifest, plan, packages, run directories, or immutable failure records are written; recovery may still finalize a previously completed immutable snapshot without contacting a provider. The preflight proves that a supported credential source is configured, not that a remote provider will authenticate it.

After every planned public record exists:

```bash
SSC03_CALIBRATION_MODEL_ID="$MODEL_ID" \
uv run aec-bench --json meta-harness lifecycle-calibration-freeze \
  --config docs/examples/meta-harness/hydraulic-lifecycle-calibration.example.yaml
```

Use the exact same `MODEL_ID` value used for campaign execution; changing it changes the requested manifest and cannot match the immutable records.

The default destination is `frozen-condition.json` inside the campaign output root. Use `--output` to select another write-once path.

The example stores generated content under the ignored repository `artefacts/` root. A real campaign must run from a clean committed checkout; otherwise records correctly remain `partial` and cannot support selection.

## What PR21 does not establish

The deterministic execution proof validates campaign and selection machinery. It is not model evidence. Until the paid public campaign runs, there is no actual selected model condition.

PR21 does not mount or evaluate the sealed pump-station target, publish private traces, estimate a causal effect, demonstrate learner transfer, perform post-training, or establish continual learning. PR22 must consume the exact freeze, run the preregistered sealed audit once, retain full private records under access control, and publish only an allowlisted redacted aggregate.
