# ABOUTME: Research report on long-horizon AI task and benchmark design for AEC-Bench.
# ABOUTME: Synthesizes benchmark construction, evaluation, multimodal, reward, and meta-harness implications.

# Long-Horizon Task Research Report

Review date: 2026-06-28

This report looks outward from AEC-Bench's current task catalogue and meta-harness direction. The immediate goal is not to copy a benchmark style wholesale. It is to extract the practical machinery behind strong long-horizon evaluations and turn that into a concrete plan for AEC-Bench task construction.

The center of gravity is long-horizon task design. Multimodal extensions are included as implementation ladders and source-pack sketches, since AEC-Bench does not yet have a real drawing/document corpus comparable to professional project records.

## Executive Read

The strongest long-horizon benchmarks are not just collections of harder prompts. They are resettable worlds with explicit initial state, action surfaces, artifacts, hidden ground truth, and verifiers. SWE-bench uses repositories and tests. WebArena and OSWorld use executable web or desktop environments. tau-bench and AppWorld use stateful API worlds and final database-state checks. PaperBench and GDPval use large deliverables and rubric-based grading. These designs make the model do work over time instead of selecting an answer.

For AEC-Bench, the closest equivalent is a composite task-world template with a product-world scenario: a generated engineering package where individual formula templates become stages in a larger design, review, or compliance workflow. The natural objects are source artifacts, handoff fields, branch decisions, compliance gates, and final deliverables.

Evaluation should be staged. The final answer still matters, but long-horizon evaluation needs intermediate checks: source extraction, unit consistency, branch selection, upstream-downstream handoff integrity, artifact completeness, collateral-damage checks, and contradiction detection. This mirrors the shift in agent RL from sparse outcome rewards toward process, grounding, and turn-level rewards.

PPO vs GRPO matters because AEC-Bench is a credit-assignment problem if it becomes a training target. GRPO is efficient and has worked well when final rewards are cheap and verifiable, as in DeepSeekMath and DeepSeek-R1. But long-horizon agent papers increasingly report that outcome-only rewards are too sparse, and that turn-level advantage estimates or verifiable process rewards are important. For AEC-Bench, the practical answer is to expose dense verifiable rewards first; algorithm choice comes after the harness can localize success and failure.

The next engineering step should be one or two composite text-first worlds with staged verifiers, followed by table/document source packs, then generated drawings. Do not start by adding images as decoration. Start by making each modality carry a parameter, assumption, branch, or compliance signal that the verifier can inspect.

## What Counts As Long-Horizon Here

A task is long-horizon when success requires sustained stateful work across multiple dependent decisions. It can be long because of:

- many action steps, as in browser, OS, terminal, or API benchmarks;
- many files or artifacts, as in software engineering benchmarks;
- many source documents or modalities, as in deep-research and multimodal browsing tasks;
- many staged subgoals, as in research replication or professional deliverable tasks;
- many dependent calculations and compliance checks, as in AEC workflows.

For AEC-Bench, horizon should not be measured only by token count or number of formula calls. A good composite task forces the model to preserve design state over multiple transformations: extract source facts, choose assumptions, calculate intermediate values, pass values downstream, select governing cases, produce a compact design record, and defend it with evidence.

## Benchmark Construction Patterns

| Pattern | Examples | Construction Unit | Evaluation Signal | AEC-Bench Lesson |
| --- | --- | --- | --- | --- |
| Repository issue world | [SWE-bench](https://arxiv.org/abs/2310.06770), [SWE-Bench Pro](https://arxiv.org/abs/2509.16941), [SWE-bench Multimodal](https://arxiv.org/abs/2410.03859) | Real issue, repo checkout, tests, sometimes visual issue artifacts | Unit/integration tests and patch application | Build tasks around a persistent working package, not a single answer. Verify final artifacts and hidden tests. |
| Realistic web world | [WebArena](https://arxiv.org/abs/2307.13854), [VisualWebArena](https://arxiv.org/abs/2401.13649), [WorkArena](https://arxiv.org/abs/2403.07718) | Website state, account data, browser action surface, manuals or knowledge bases | Functional task completion, state inspection, sometimes multimodal observations | AEC tasks need source material plus action surface. A model should navigate and assemble evidence, not just solve a printed equation. |
| OS and mobile control world | [OSWorld](https://arxiv.org/abs/2404.07972), [AndroidWorld](https://arxiv.org/abs/2405.14573) | VM or device state, real apps, setup and teardown scripts | Execution-based state checks and retrieved artifacts | Reset and post-processing are first-class harness features. AEC composite worlds need reproducible source-pack setup and result retrieval. |
| Stateful API and tool world | [tau-bench](https://arxiv.org/abs/2406.12045), [tau2-bench](https://arxiv.org/abs/2506.07982), [ToolSandbox](https://arxiv.org/abs/2408.04682), [AppWorld](https://arxiv.org/abs/2407.18901) | Database state, policy docs, tools, simulated user, API side effects | Final database state, goal-state match, pass^k reliability, intermediate milestones | AEC-Bench should model engineering packages as stateful worlds with side effects and handoff fields, not only final numeric answers. |
| Open-ended research or work product | [GAIA](https://arxiv.org/abs/2311.12983), [BrowseComp](https://arxiv.org/abs/2504.12516), [PaperBench](https://arxiv.org/abs/2504.01848), [GDPval](https://arxiv.org/abs/2510.04374), [HCAST](https://arxiv.org/abs/2503.17354) | Question, source pack or real-world deliverable, sometimes human baseline | Short answer, expert rubric, hierarchical subtask scores, human-time calibration | Some AEC tasks will need rubric or expert-style scoring, but the first pass should maximize deterministic subchecks. |
| High-fidelity RL environment | [EnterpriseGym Corecraft](https://arxiv.org/abs/2602.16179), agent RL worlds | Large simulated organization or domain, tool set, expert-authored rubrics | Rubric criteria and held-out task pass rates | If AEC-Bench becomes training infrastructure, task realism and reward quality matter as much as model size. |

The recurring construction formula is:

1. Define a world state that persists across steps.
2. Give the agent an action surface.
3. Provide source material that contains necessary but not always explicit facts.
4. Specify hidden target state or artifact constraints.
5. Reset the world for each run.
6. Verify the final state and enough intermediate state to localize failures.

## Evaluation Patterns

The important shift is from answer grading to state and artifact grading.

### Final-State Verification

Stateful benchmarks often inspect the end state rather than the textual answer. tau-bench compares the final database state with an annotated goal state and adds pass^k to measure reliability across repeated trials. AppWorld uses state-based unit tests and checks for collateral damage. AndroidWorld and OSWorld initialize a device or VM, run the agent, then inspect device or application state.

AEC-Bench implication: composite tasks should have a hidden `gold_state.json` or equivalent with final handoffs, compliance flags, selected cases, and expected deliverable properties. A final narrative can be graded, but the core score should come from structured state.

### Hidden Tests And Artifact Equivalence

SWE-bench style tasks evaluate patches against tests. This is a powerful pattern because there are multiple possible implementations but objective behavioral checks. AppWorld extends the same idea to API worlds: different action paths can be correct if the final state is right and no unexpected state was damaged.

AEC-Bench implication: a long-horizon engineering task can allow multiple solution narratives, but the artifact contract must be explicit. For example, a pump-station package can be correct if the duty point, headloss, NPSH margin, motor input power, and branch decisions match the hidden state within tolerances.

### Execution-Based Evaluation

OSWorld is useful because each task has setup configuration and custom execution-based evaluation scripts. It also exposes the ugly truth: real tasks require task-specific getters, post-processing, and evaluation functions.

AEC-Bench implication: there is no avoiding task-specific verifiers. The scalable route is to make verifier components reusable: source extraction checks, formula closure checks, table comparison, drawing measurement comparison, unit normalization, handoff equality, branch gate checks, and contradiction ledgers.

### Reliability Over Repeated Runs

tau-bench's pass^k metric is a good long-horizon signal because a model that succeeds once but behaves inconsistently is not reliable. Long-horizon tasks amplify small stochastic failures.

AEC-Bench implication: composite suites should report pass@1 and pass^k style reliability. This matters especially when tasks include branch decisions or source interpretation.

### Human-Time Calibration

HCAST measures task duration for humans, using skilled participants under comparable conditions. SWE-Bench Pro also frames long-horizon software tasks as work that may take professionals hours to days. This grounds difficulty in real-world effort, not only model score.

AEC-Bench implication: we should assign human-effort bands to composite tasks: 5 minutes, 20 minutes, 1 hour, half day. Even rough SME estimates will help interpret model results.

### Rubrics And Hierarchical Subtasks

PaperBench decomposes research replication into thousands of gradable rubric items. GDPval uses industry-professional tasks and deliverable quality evaluation. These are less deterministic than formula tasks but more faithful to real work.

AEC-Bench implication: deterministic calculation stages should remain the backbone. Rubrics become useful for final engineering memos, option selection, and review quality once structured state checks have done the objective work.

## Reward And Training Lessons

### Sparse Outcome Rewards Are Not Enough

Classic final-answer rewards are attractive because they are simple. But long-horizon tasks create a credit-assignment problem: a model can extract the right source value and fail later, or succeed numerically while citing the wrong source or choosing an invalid branch.

Recent process-reward work points in the same direction. [Let's Verify Step by Step](https://arxiv.org/abs/2305.20050) found process supervision outperforming outcome supervision for multi-step math. [Verifiable Process Rewards](https://arxiv.org/abs/2605.10325) argues that dense turn-level supervision from symbolic or algorithmic oracles can improve long-horizon credit assignment. [LongRLVR](https://arxiv.org/abs/2603.02146) makes the long-context version especially relevant: outcome-only reward can fail to train contextual grounding, while explicit evidence rewards help.

AEC-Bench should expose rewards for:

- correct source selection;
- correct parameter extraction;
- correct unit conversion;
- correct branch or governing-case selection;
- upstream-downstream handoff consistency;
- final formula closure;
- compliance decision correctness;
- artifact completeness;
- absence of contradictions between the produced answer and structured state.

### PPO And GRPO

[PPO](https://arxiv.org/abs/1707.06347) is a policy-gradient method with a clipped objective and commonly uses a learned value function for advantage estimation. Its practical strength for long-horizon tasks is that it fits the Markov decision process setting: states change, actions happen over time, and a critic can estimate which turns or states contributed to reward.

[DeepSeekMath](https://arxiv.org/abs/2402.03300) introduced GRPO as a PPO variant that improves memory usage by removing the critic and estimating advantages from groups of sampled outputs. [DeepSeek-R1](https://arxiv.org/abs/2501.12948) then used GRPO with rule-based accuracy and format rewards for reasoning training. This is a major result for verifiable reasoning: the reward can be simple and objective, and the model can improve through large-scale RL.

The catch is horizon. [Turn-PPO](https://arxiv.org/abs/2512.17008) argues that directly applying GRPO to multi-turn agent tasks creates instability, because different turns contribute unequally to final reward. It reports PPO as more robust than GRPO in those settings and proposes turn-level MDP formulation. A separate GRPO study, [Learning Without Critics?](https://arxiv.org/abs/2511.03527), reports that learned critics remain important in long-horizon classical RL settings.

The right AEC-Bench implication is not "pick PPO" or "pick GRPO" today. It is: make the harness capable of producing dense, reliable, stage-local reward records. With that in place, PPO, GRPO, turn-level PPO, or future agent RL variants can actually learn useful credit assignment.

### GLM-5.2, GLM-5.1, And Long-Horizon Agentic Engineering

The official [Z.ai GLM-5 repository](https://github.com/zai-org/GLM-5) now describes GLM-5.2 as a flagship model for long-horizon tasks with a 1M-token context, stronger coding capability, and reported gains on Terminal-Bench 2.1 and SWE-bench Pro. The same README describes GLM-5.1 as staying productive over longer agentic sessions, including repeated iteration over hundreds of rounds and thousands of tool calls.

The primary technical report linked by that repository is still [GLM-5: from Vibe Coding to Agentic Engineering](https://arxiv.org/abs/2602.15763). It claims asynchronous reinforcement learning infrastructure and asynchronous agent RL algorithms that improve learning from complex, long-horizon interactions.

AEC-Bench implication: frontier model work is explicitly optimizing long-context, long-horizon, tool-rich engineering tasks. AEC-Bench can be valuable if it provides the thing these systems need but generic coding benchmarks do not: realistic engineering source packs, calculation closure, discipline handoffs, and verifiable project-style artifacts.

## AEC-Bench Task Construction Model

The recommended unit is a composite task-world template whose scenario is an AEC product world.

An AEC product-world scenario becomes a generated task package with:

- a task graph made from existing templates and handoff fields;
- source artifacts that carry parameters, constraints, branch conditions, and evidence;
- a world sidecar that declares hidden ground truth and operation handles;
- one or more required deliverables;
- a staged verifier that checks source grounding, calculation closure, handoffs, compliance, and final artifact state;
- a run ledger that records model actions, produced artifacts, verifier outputs, and failure localization.

### Minimal Composite Task-World Payload

The first version can stay simple:

```yaml
world_id: pump-station-duty-electrical-001
discipline_scope:
  - civil
  - mechanical
  - electrical
task_graph:
  - id: design_flow
    template: rational-method
    outputs: [design_flow_m3_s]
  - id: headloss
    template: hazen-williams-friction
    inputs: [design_flow_m3_s]
    outputs: [friction_head_m]
  - id: pump_power
    template: pump-power-efficiency
    inputs: [design_flow_m3_s, friction_head_m]
    outputs: [motor_input_kw]
source_artifacts:
  - id: pump_curve
    type: table
    carries: [pump_efficiency, npshr]
  - id: pipe_schedule
    type: table
    carries: [diameter_mm, length_m, material]
handoffs:
  design_flow_m3_s:
    producer: design_flow
    consumers: [headloss, pump_power]
branch_decisions:
  governing_head_case:
    allowed: [static_head, friction_head, total_dynamic_head]
verifier:
  gates:
    - source_grounding
    - formula_closure
    - handoff_consistency
    - branch_decision
    - final_artifact_contract
```

This mirrors existing meta-harness handles already appearing in the task-world notes: `source_artifacts`, `handoffs`, `branch_decisions`, and `compliance`.

## Composite Task Pilots

These are the best first candidates because they combine existing deterministic templates into real engineering packages.

| Pilot | Current Ingredients | Long-Horizon Sequence | Source Pack | Staged Verifier |
| --- | --- | --- | --- | --- |
| Stormwater drainage package | Rational method, detention, pipe hydraulics, outlet checks | Extract catchment and rainfall, compute pre/post-development flows, size detention, check outlet and pipe reach | Catchment plan, rainfall table, council release note, basin section, pipe long section | Source values, peak-flow handoff, detention volume, outlet capacity, pipe velocity/HGL, final compliance |
| Pump station duty package | Hazen-Williams, Darcy, pump power, NPSH, motor input | Build system curve, calculate losses, choose duty point, compute shaft and motor power, check NPSH | Pump curve, system schematic, pipe schedule, suction vessel data, motor schedule | Flow/head handoff, friction closure, NPSH margin, duty branch, motor load |
| Fire-water supply and sprinkler demand | Hydrant curve, sprinkler flow, pipe friction, residual pressure | Derive available flow, calculate demand, subtract losses and elevation, decide margin | Hydrant flow test, water-supply curve, sprinkler layout, pipe schedule | Curve fit, demand sum, pressure loss, residual pressure, pass/fail |
| Road and rail alignment package | Curve elements, superelevation, cant, spiral, stopping sight distance | Extract geometry, compute curve identities, clamp superelevation/cant, evaluate sight and speed | Alignment plan, chainage schedule, criteria table, vertical profile | Chainage closure, criteria source, clamp decisions, speed/sight compliance |
| Wind-to-facade structural package | Wind speed, pressure, effective wind area, bracket load, thermal movement | Derive wind action, apply tributary area, check bracket loads and movement allowance | Site plan, wind region table, pressure-zone drawing, facade elevation, bracket detail | Source region, pressure calculation, area extraction, load handoff, bracket utilisation |
| Civil-ground retaining interface | Rankine pressure, wall stability, bearing pressure, groundwater | Compare civil and ground assumptions, calculate active/passive forces, check external stability | Wall section, geotech log, groundwater record, surcharge plan | Theory selection, water branch, force closure, overturning/sliding/bearing pass flags |
| Treatment process to aeration and power | BOD load, nitrification SRT, oxygen demand, blower/power handoff | Build process basis, check SRT, compute oxygen demand, pass electrical load | Process flow diagram, lab table, basin schedule, blower schedule, electrical load list | Load extraction, SRT gate, oxygen demand, power handoff, compliance |
| PV and storage feeder package | PV DC/AC, string voltage, DC drop, BESS usable capacity, feeder drop | Configure string, estimate energy/loss, size storage, check feeder and voltage drop | PV layout, module datasheet, inverter datasheet, BESS duty table, cable schedule | String bounds, voltage drop, BESS capacity, feeder current, final energy/load record |
| Earthing and arc-flash package | Fault current, grid resistance, GPR, arc flash, busbar force | Compute fault levels, earthing response, arc incident energy, switchboard force | Single-line diagram, transformer datasheet, earthing layout, switchboard detail, protection study | Impedance chain, GPR, incident energy, PPE category, busbar stress |
| Rail braking and signalling package | Davis resistance, tractive/braking power, stopping distance, signal overlap | Compute train resistance, braking distance, sighting/overlap, level-crossing strike-in | Rolling stock datasheet, route gradient, braking curve, signal layout | Gradient sign, braking closure, overlap clearance, signal compliance |

The first two pilots should be text/table only. That keeps the problem focused on task graph, handoff, source evidence, and staged verification before drawing extraction adds noise.

## Harness Engineering Requirements

### 1. Composite Task-World Template Compiler

AEC-Bench needs a compiler that takes a composite task-world template spec and emits:

- task graph;
- generated source pack;
- hidden world state;
- model-facing prompt;
- expected output contract;
- verifier config;
- scoring rubric;
- run directory layout.

This compiler should compose existing template generators rather than duplicate formulas.

### 2. Source Artifact Generator

The generator must create artifacts that carry real task facts. Early artifact types:

- scalar briefing note;
- CSV/table;
- Markdown design memo;
- simple HTML/PDF datasheet;
- generated drawing as SVG or image with known geometry;
- mixed source pack with deliberate distractors.

Each artifact should declare the fields it carries. The verifier should know whether a value came from `pipe_schedule`, `rainfall_table`, `pump_curve`, or `alignment_plan`.

### 3. Staged Verifier

The staged verifier should emit a failure-localized score:

```json
{
  "overall": "fail",
  "score": 0.62,
  "gates": {
    "source_grounding": {"score": 0.8},
    "handoff_consistency": {"score": 1.0},
    "branch_decision": {"score": 0.0},
    "formula_closure": {"score": 0.7},
    "final_artifact_contract": {"score": 0.6}
  }
}
```

This is also the reward surface for training. It is the bridge between benchmark and RL.

### 4. Evidence Ledger

Every run should preserve:

- model answer;
- structured extraction, if requested;
- generated deliverables;
- source citations;
- intermediate values;
- verifier output;
- contradiction ledger;
- timing and token/cost metadata;
- optional trajectory/action log.

This makes meta-harness repair possible. Without a ledger, every failure is an anecdote.

### 5. Handoff And Unit Contract

Long-horizon AEC tasks will fail quietly if unit systems drift. Handoff fields need declared units, tolerances, producer, consumer, and acceptable rounding.

Example:

```yaml
handoffs:
  design_flow:
    unit: L/s
    tolerance: 0.5
    producer_stage: hydrology
    consumer_stages: [pipe_hydraulics, detention]
```

### 6. Multimodal Extractors As Optional, Not Magical

The first multimodal extension should not require perfect computer vision. Generated artifacts can include known geometry and hidden metadata for verification. The model still sees the raster or PDF, but the harness knows the truth.

### 7. Reliability Metrics

For composite worlds, report:

- pass@1;
- pass^k or repeated-run reliability;
- average gate score;
- source-grounding score;
- handoff consistency score;
- contradiction rate;
- action/turn count;
- token/cost budget;
- human-effort band.

## Multimodal Extension Ladder

| Level | Source Pack | What Model Must Do | Harness Requirement | Risk |
| --- | --- | --- | --- | --- |
| 0 | Text-only generated brief | Solve staged calculations and handoffs | Composite task graph and staged verifier | Low realism |
| 1 | Tables and simple docs | Extract parameters from source tables and memos | Table/doc artifact generator, source-grounding verifier | Wrong value may look numerically plausible |
| 2 | Generated drawings | Read geometry, chainage, elevations, layout membership | Drawing generator with hidden geometry truth, visual extraction gates | Vision errors can dominate task quality |
| 3 | Mixed office package | Cross-reference drawings, schedules, datasheets, and memos | Source registry, artifact references, contradiction ledger | Context management and source conflict |
| 4 | Real or SME-curated project pack | Interpret realistic AEC artifacts and produce design/review deliverable | Governance, licensing, redaction, expert review, harder rubrics | Data rights and ambiguous ground truth |

Good multimodal AEC tasks should make the modality necessary. A catchment plan should determine area or slope. A pump curve should determine efficiency or NPSHr. A facade elevation should determine tributary area. A signal layout should determine overlap or clearance. If the image is only decorative, it should not be in the benchmark.

## Meta-Harness Opportunities

The meta-harness should operate over task worlds, not over raw prose alone.

### Product Operation

Combine two or more worlds by matching declared handoff fields. Example: `rational_method.peak_flow` becomes `pipe_hydraulics.design_flow`. The operation is valid only if units and tolerances line up.

### Projection Operation

Render the same world in different modalities:

- scalar text;
- table source;
- drawing source;
- document source;
- mixed package.

This gives controlled multimodal experiments where the underlying world is fixed.

### Difficulty Difference Operation

Move difficulty by removing explicit values, adding distractor rows, increasing source count, adding branch ambiguity, tightening tolerances, or requiring a deliverable artifact. The operation should preserve ground truth.

### Scenario Portfolio Operation

Create a family of related cases with shared source artifacts but different load, season, tide, fire, occupancy, or operating scenarios. This is especially natural for AEC because design is often about governing cases.

### Repair Operation

When a run fails, use gate output to propose a task repair:

- missing source handle;
- ambiguous source artifact;
- verifier too final-answer-only;
- hidden state lacks branch decision;
- task graph has a unit mismatch;
- source pack allows multiple valid interpretations.

The harness should record the repair proposal, but harness-owned code should apply validated operations.

### Contradiction Operation

Detect answers where final numeric output passes but the evidence or deliverable contradicts the hidden state. This matters in AEC because a plausible report can contain the wrong source or branch assumption while landing near the right number.

## Recommended Next Steps

1. Select two composite pilots:
   - stormwater drainage package;
   - pump station duty package.

2. Define the first composite task-world payload:
   - task graph;
   - source artifacts;
   - handoffs;
   - branch decisions;
   - compliance gates;
   - final artifact contract.

3. Build a text/table source-pack generator:
   - no drawings yet;
   - source artifacts must carry hidden values;
   - include at least one distractor source row.

4. Implement staged verifier output:
   - source grounding;
   - formula closure;
   - handoff consistency;
   - branch decision;
   - final artifact contract.

5. Add reliability evaluation:
   - repeated runs;
   - pass@1 and pass^k;
   - gate-level score distribution.

6. Add one multimodal projection:
   - pump curve or pipe long-section as generated SVG/PDF;
   - hidden geometry/table truth;
   - explicit visual extraction gate.

7. Feed outputs into meta-harness:
   - product operation;
   - projection operation;
   - difficulty difference operation;
   - repair operation.

## Near-Term Deliverable Shape

The first composite world should produce a run directory like:

```text
runs/pump-station-duty-electrical-001/
  source/
    task.md
    pipe_schedule.csv
    pump_curve.csv
    motor_schedule.md
  hidden/
    world_state.json
    verifier_config.json
  agent/
    output.md
    structured_answer.json
  verifier/
    result.json
    gates.json
    contradictions.json
```

This is close to AEC-Bench's current artifact discipline and Harbor-shaped execution. It also keeps the path open for later browser/OS or tool-agent tasks without forcing them into the first milestone.

## Design Principles For AEC-Bench Long-Horizon Tasks

- Compose existing templates before writing new domain logic.
- Use source artifacts to carry required facts, not to decorate prompts.
- Make handoff fields explicit and unit-checked.
- Score intermediate gates as well as the final answer.
- Preserve full run evidence.
- Include collateral-damage checks when tasks mutate artifacts.
- Prefer deterministic verifiers where possible.
- Use rubrics only for genuinely non-deterministic deliverable quality.
- Report reliability, not only best attempt.
- Treat meta-harness operations as auditable proposals applied through harness-owned code.

## Bibliography

- [SWE-bench: Can Language Models Resolve Real-World GitHub Issues?](https://arxiv.org/abs/2310.06770)
- [SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?](https://arxiv.org/abs/2509.16941)
- [SWE-bench Multimodal: Do AI Systems Generalize to Visual Software Domains?](https://arxiv.org/abs/2410.03859)
- [WebArena: A Realistic Web Environment for Building Autonomous Agents](https://arxiv.org/abs/2307.13854)
- [VisualWebArena: Evaluating Multimodal Agents on Realistic Visual Web Tasks](https://arxiv.org/abs/2401.13649)
- [OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments](https://arxiv.org/abs/2404.07972)
- [AndroidWorld: A Dynamic Benchmarking Environment for Autonomous Agents](https://arxiv.org/abs/2405.14573)
- [WorkArena: How Capable Are Web Agents at Solving Common Knowledge Work Tasks?](https://arxiv.org/abs/2403.07718)
- [tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains](https://arxiv.org/abs/2406.12045)
- [tau2-bench: Evaluating Conversational Agents in a Dual-Control Environment](https://arxiv.org/abs/2506.07982)
- [ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use Capabilities](https://arxiv.org/abs/2408.04682)
- [AppWorld: A Controllable World of Apps and People for Benchmarking Interactive Coding Agents](https://arxiv.org/abs/2407.18901)
- [GAIA: a benchmark for General AI Assistants](https://arxiv.org/abs/2311.12983)
- [BrowseComp: A Simple Yet Challenging Benchmark for Browsing Agents](https://arxiv.org/abs/2504.12516)
- [PaperBench: Evaluating AI's Ability to Replicate AI Research](https://arxiv.org/abs/2504.01848)
- [GDPval: Evaluating AI Model Performance on Real-World Economically Valuable Tasks](https://arxiv.org/abs/2510.04374)
- [HCAST: Human-Calibrated Autonomy Software Tasks](https://arxiv.org/abs/2503.17354)
- [EnterpriseGym Corecraft: Training Generalizable Agents on High-Fidelity RL Environments](https://arxiv.org/abs/2602.16179)
- [Proximal Policy Optimization Algorithms](https://arxiv.org/abs/1707.06347)
- [DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models](https://arxiv.org/abs/2402.03300)
- [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948)
- [Let's Verify Step by Step](https://arxiv.org/abs/2305.20050)
- [Verifiable Process Rewards for Agentic Reasoning](https://arxiv.org/abs/2605.10325)
- [LongRLVR: Long-Context Reinforcement Learning Requires Verifiable Context Rewards](https://arxiv.org/abs/2603.02146)
- [Turn-PPO: Turn-Level Advantage Estimation with PPO for Improved Multi-Turn RL in Agentic LLMs](https://arxiv.org/abs/2512.17008)
- [Learning Without Critics? Revisiting GRPO in Classical Reinforcement Learning Environments](https://arxiv.org/abs/2511.03527)
- [GLM-5: from Vibe Coding to Agentic Engineering](https://arxiv.org/abs/2602.15763)
- [Z.ai GLM-5 repository and GLM-5.2 README](https://github.com/zai-org/GLM-5)
