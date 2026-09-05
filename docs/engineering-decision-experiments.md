# Engineering decision experiments

| Field | Value |
| --- | --- |
| Class | Guide |
| Status | Current |
| Owner | Experimentation and task owners |

The library supplies hydraulic lineage generation and revision checks, costed dam
investigation semantics, and public pump handover assessment. Four separate
experiments consume these capabilities: hydraulic counterfactuals, dam investigations,
pump handover continuation, and verifier challenges. A qualification command checks
the same experiments against stated control expectations. It uses deterministic
controls through the existing lifecycle and actor runtimes. It does not call a model,
train weights, establish transfer, or certify real engineering decisions.

Run one experiment from the repository root, with development dependencies installed:

```bash
uv run python -m aec_bench.experimentation.engineering_decisions dam \
  --output /tmp/aec-dam-investigation
```

The other choices are `hydraulic`, `pump`, and `verifier`. Supply `--definition`
with a JSON condition definition or a previous `experiment.json` to repeat those
conditions in a new output directory. The saved definition declares seeds and
partitions, revisions, profiles, policies, action limits, or the closing horizon,
as applicable. Duplicate conditions and lineage assignments are rejected.

Each experiment saves its definition and `PlannedTrial` values before execution.
Hydraulic execution uses `run_lifecycle_trial()`. Dam and pump execution use
`run_world_experiment()` with deterministic controllers and the existing world
hosts. All return ordinary `TrialRecord` values and publish them through the
ledger writer. Records retain the experiment definition, diagnostics,
and execution evidence. Pump records also retain the existing world repository
files in a `world_run` ZIP artifact. Restore it to a private directory, with
owner-only directory access and file read/write permissions, before opening the
canonical repository. Repeat conditions with the same pinned library revision or
package build and dependency environment. Source references remain in the normal
run manifests; a control record with unresolved source does not establish code provenance.

The controls are explicit Python policies. This command does not select arbitrary
model adapters. Model comparisons can use the domain capabilities through their
normal lifecycle or world runner, with a separately declared experiment.

Run qualification for all four experiments:

```bash
uv run python -m aec_bench.experimentation.qualification.engineering_decisions \
  --output /tmp/aec-engineering-decisions
```

The destination must be empty. `--seeds 2 8 12` selects the default synthetic project
lineages. The command returns non-zero when a control fails its stated expectation.
The root `qualification.json` records checks, source hashes, and projections of
the retained trial diagnostics. It does not define a second reward.
Each experiment has its own `experiment.json` and `ledger/`. Hydraulic packages
and durable pump runs remain beside them for inspection. Output contains verifier
diagnostics and public synthetic examples labelled for intended acceptance use;
keep it private when preparing a later acceptance bank.
The command creates a new output directory with owner-only access.

## Hydraulic changes and generated data

`HydraulicLineage` varies catchment area, correlated basin area, and rainfall within
narrow synthetic ranges. Each seed produces one baseline and the existing
administrative, rainfall, outlet, and tailwater revision siblings. The lifecycle
materializer accepts `lineage=HydraulicLineage(seed=...)`; ordinary materialization
continues to use the authored calibration sources.

The hydraulic experiment assigns each seed to exactly one explicit train, development,
or acceptance partition before it expands revision siblings. `HydraulicLineage` has
no split policy. Every sibling remains with its project. Custom qualification seed
lists use the development partition; the default experiment declares all three. These labels do not make the
qualification output a sealed acceptance set. Freeze and protect a separate bank
before using it for a learning claim. Nearby scalar variants do not establish
mechanism or topology transfer, and the ranges are not an SME-calibrated distribution.

The package validator regenerates the expected sources from the recorded seed.
The normal solver, operation resolver, checkpoint runtime, and eleven-gate verifier
then execute the lifecycle. The resolver's actual input projections determine
retention and invalidation. The verifier no longer contains a second revision-to-reuse
lookup table. The report separates physical readiness from valid reporting of a
physical failure.

## Investigation cost and delay

Dam scenarios can declare `SeepageInvestigation`: investigation credits, response
deadline, action prices, and inspection durations. These values are public task
constraints. Accepted investigations consume credits. Rejected investigations do
not change state. A confirmation reading advances time to at least its scheduled
time; inspections add their declared duration. Late submissions remain observable
but cannot be successful. Existing scenarios without this declaration retain their
cost-free, untimed behaviour.

The three costed scenarios are registered, content-pinned world profiles.
The qualification includes two identical opening observations with different hidden
instrument conditions, plus an urgent fault case. Its observation-only control checks
the instrument, escalates on released fault evidence, or completes the evidence
needed for routine surveillance. The experiment applies evidence-first, unsupported-response, and delayed-response
controls to every selected profile. Qualification checks the relevant contrasts.

Outcome correctness, evidence completeness, timeliness, expenditure, and rejections
remain separate fields. The private exhaustive search reports a **perfect-information
minimum cost**. It is a lower bound for each hidden scenario, not a feasible policy
or a measured expected value of information. Scenario construction and task semantics
belong to the dam owner; qualification and policy comparisons belong to experimentation.

## Pump continuation and handover

The pump control creates independent runs from the same registered opening state and
uses the same absolute closing horizon. One handover contains the public verification
work item; the other omits it. A fresh actor host chooses whether to start that work
from the handover. The normal actor interface advances time, and the existing host
policy applies eligible Operations reviews. Neither control receives new authority.
A completed continuation must replay successfully and close at exactly the requested
world boundary. The action limit counts the initial verification request and continuation actions.
Exhausting that limit produces a failed, truncated
trial with its observed closing time; it cannot claim the requested horizon was reached.

`PumpHandover` carries facts from one released actor view: clocks, duty assignment,
restrictions, liabilities, accepted evidence and its health, resources and schedules,
work, active processes, and physical boundaries. Its assessment identifies omitted,
contradicted, invented, and stale information. The source view identity binds the
assessment to an exact observation. A handover is a communication artifact, not a
second world state or an approval.

The deliberately weak omitted-work control measures a causal consequence of missing
handover content. It does not demonstrate that a model can recover from incomplete
records. The horizon is a bounded continuation, not complete operational success.
The existing frozen `handover_omission_count` field stays reserved and unmeasured;
the explicit `handover_assessment` in this experiment has its own defined scope.

## Verifier challenge cases

The hydraulic control changes actor submissions **before** host acceptance. Cases
include stale source identity, missing memo evidence, false readiness, and an
unsupported authority claim. A reordered but consistent decision list is a positive
control. The command records expected and observed acceptance, including individual
gate failures. These cases are maintained examples, not proof against every exploit.

Permanent tests also cover budget rejection, correct answers without sufficient
evidence, late supported answers, handover omissions and contradictions, and exact
pump replay. Do not turn deterministic control success into a model-performance,
real-project, or RL-readiness claim. Weight training and its hosted integration remain
separate work.

## Hydraulic training qualification

Run the local Prime qualification with the `prime` extra installed. From an
installed environment, use a working directory outside the repository root:

```bash
python -m aec_bench.experimentation.qualification.hydraulic_training \
  --output /tmp/aec-hydraulic-training
```

The repository's `agents/` directory can shadow the `openai-agents` dependency
when Python starts from the repository root. The output directory must be empty.
Use `--definition` to supply a `HydraulicExperiment` JSON file with non-empty
train, development, and acceptance partitions. The default uses the existing
synthetic hydraulic lineages and four revision conditions.

The qualification assigns complete project lineages before materializing their
revision siblings. It generates acceptance fixtures separately and excludes them
from the Prime package. These are public synthetic fixtures assigned to an
acceptance partition; they are not an independently sealed benchmark holdout.

The output contains:

- `definition.json`: generation conditions and partition membership.
- `reference_trials/`: ordinary planned trials and ledger evidence from the
  existing deterministic hydraulic experiment.
- `environments/aec_hydraulic_training/`: a generated local Verifiers package
  containing training and development groups.
- `prime_controls/`: transcripts and task-verifier results from replay through
  the actual Prime lifecycle tool interface.
- `training_demonstrations.jsonl`: only successful training-group controls,
  represented as messages and OpenAI-format tool definitions. Environment
  observations are tool messages. Hidden verifier results and group metadata
  are not model inputs. These are scripted demonstrations, not model samples.
- `training.toml`: a one-step hosted handoff using the existing small-model
  default. The environment ID resolves only after that package is installed or
  published through an approved deployment procedure.
- `qualification.json`: local checks, installed versions, package requirements,
  and separate hosted-run and weight-update status.

The command makes no provider calls. It checks terminal reward agreement,
zero reward for incomplete work, and isolation between rollouts. A local pass
establishes the tested tool and reward boundary. It does not establish a model
weight update, SFT token-mask correctness, hosted dependency compatibility,
physical-distribution coverage, or generalization. The generator still uses
narrow synthetic parameter ranges and the existing calculation structure.

The exported package pins the installed Prime dependency closure. Its retained
source archive uses package-relative paths and includes those exact versions.
The loader checks both source bytes and installed versions before accepting a
rollout. Install the bound AEC-Bench wheel and generated environment together;
a package version alone does not establish source equivalence.

Before running training, verify the hosted Python and Verifiers versions against
the generated package, install the bound AEC-Bench source, and confirm the model
is available. For the SFT-to-RL comparison, verify that the RL run can start from
the exact SFT checkpoint. The current open-source Prime trainer and the local
AEC-Bench lifecycle package require different Python and Verifiers versions;
these are separate runtime checks, not resolved by generating TOML.

`aec-bench prime train-config --checkpoint-id` records an explicit Prime
checkpoint. The generated configuration targets the pinned Prime CLI. It uses
`eval.eval_base_model` and explicit `[[eval.env]]` entries with `split="eval"`,
so the CLI includes evaluation in its API request. The command rejects the
removed difficulty-buffer options. `aec-bench prime train` rejects incompatible
fields and evaluation-only training splits before invoking Prime.
Prime retains ownership of complete configuration and model validation. See
[Prime's configuration reference](https://docs.primeintellect.ai/hosted-training/advanced-configs).
