# ABOUTME: Methodology for building long-horizon composite task-world templates.
# ABOUTME: Defines the compiler boundary, harness requirements, and meta-harness pass points.

# Composite Task-World Methodology For Long-Horizon Products

Long-horizon product worlds are composite task-world templates: staged engineering packages that compile into the existing `TaskWorldProfile` and meta-harness world payload contracts.

This is an authoring layer, not a new execution boundary. A composite template records source artifacts, stages, handoff fields, branch decisions, verifier gates, and final deliverables, then emits the task-world artifacts that existing harness and meta-harness machinery can consume.

## Boundary Decision

Use one executable abstraction:

- `CompositeTaskWorldTemplate` is the authoring object.
- `TaskWorldProfile` and the compiled world payload are the execution and meta-harness objects.
- A product world is the engineering scenario inside the template: drainage package, pump-station note, facade fixing package, and so on.
- Long-horizon is a difficulty and evaluation property of the compiled template, not a separate class, script, CLI namespace, or verifier family.

This keeps composite products inside the same task-world contracts as the meta-harness. Future harness engineering should extend the compiler, materializer, source adapters, stage runners, ledgers, and verifier gates around this contract rather than creating a parallel long-horizon runtime.

The goal is not simply "more steps". The goal is a task where a model must preserve engineering meaning across time: read source evidence, choose the right regime, compute intermediate results, carry those results forward, notice contradictions, and produce a package that a verifier can audit.

## Product-World Template

Every composite task-world template for a long-horizon product should have these fields:

| Field | Purpose | Current contract location |
| --- | --- | --- |
| `template_id` | Stable benchmark id. | `CompositeTaskWorldTemplate.template_id` |
| `discipline_scope` | Disciplines touched by the product scenario. | Product-world scenario and operation handle payload |
| `source_artifacts` | Documents, drawings, tables, datasheets, photos, or model extracts that carry the problem values. | Projected through `source_pack` |
| `stages` | Ordered engineering stages, each with live template references. | Projected through `stage_graph` |
| `handoffs` | Named intermediate outputs that become downstream inputs. | Composed through `handoff_chain` |
| `branch_decisions` | Regime, standard, or interpretation choices that must stay explicit. | Checked by branch-consistency gates |
| `verifier_gates` | Deterministic closure checks for source, calculation, handoff, branch, and deliverable evidence. | Converted into `TaskWorldProfile.logic_profile.closure_gates` |
| `deliverables` | Final artifacts expected from the agent. | Converted into construction gates |
| `data_gaps` | What is still missing to run the product against real projects. | Subsettable through `data_gaps` |
| `operation_handles` | Meta-harness affordances for projection, product, subset, and difference operations. | Emitted in `world.json` |

## Construction Loop

Use this loop for each composite template:

1. Select the engineering product, not the formula.
   The product should resemble a real design handoff: drainage memo, pump selection note, fire-water note, rail signalling note, facade bracket note, and so on.

2. Anchor it to live templates.
   Every stage should name existing built-in templates where possible. If a required step has no template, record that as a data gap or future template requirement rather than silently inventing a result.

3. Define the source pack.
   Start with text/table sources because they are easiest to verify. Add drawings, sections, plans, datasheets, images, or GIS/BIM/model extracts only when the verifier has a way to preserve source authority.

4. Define the stage graph.
   Each stage records consumed source artifacts or handoff keys, produced handoff keys, branch decisions, and verifier gates.

5. Define handoff fields.
   Handoffs must be stable, unit-bearing, and unique. These are the spine of long-horizon scoring because they let us detect plausible arithmetic with broken engineering continuity.

6. Define branch decisions.
   Regime choices such as outlet control, hazard class, reactor model, soil model, conductor material, grade sign convention, or facade zone must be explicit fields, not hidden prose.

7. Define verifier gates.
   Use a staged gate set: source grounding, branch consistency, handoff consistency, calculation closure, and deliverable completeness.

8. Compile and materialize a runnable example.
   Each template should write `template.json`, `world.json`, `source/task.md`, hidden state, verifier config, an example structured answer, and `verifier/result.json`.

9. Record data gaps.
   Data gaps are not failures. They are the bridge from executable benchmark examples to real project tasks.

10. Run the meta-harness pass.
    Ask what can be projected, combined, subsetted, compared, repaired, or regenerated at the task-world level.

## Harness Engineering Requirements

The current implementation adds the first native catalogue/compiler substrate:

- `src/aec_bench/task_world_templates/contracts.py` defines `CompositeTaskWorldTemplate` and compilation to `TaskWorldProfile`.
- `src/aec_bench/task_world_templates/catalogue.py` defines the eleven built-in composite task-world templates.
- `src/aec_bench/task_world_templates/materializer.py` writes compiled example packages and verifies source, handoff, branch, and deliverable evidence.
- `src/aec_bench/cli/commands/task_world_templates.py` exposes `task composite-template list`, `materialize-example`, and `verify-example`.

The example package contract is:

```text
README.md
template.json
world.json
source/task.md
hidden/world_state.json
hidden/verifier_config.json
agent/structured_answer.json
verifier/result.json
deliverables/
```

The next harness layers should be added only when the examples need them:

| Requirement | Why it matters |
| --- | --- |
| Source artifact adapters | Parse real tables, drawings, PDFs, images, GIS, BIM, or model exports into source-authoritative fields. |
| Stage-level runners | Execute template instances stage by stage instead of only verifying the structured example. |
| Handoff ledger | Record produced, consumed, changed, missing, or contradicted handoffs over the run. |
| Branch-decision ledger | Preserve regime choices and the source evidence used to choose them. |
| Dense verifier records | Score intermediate closure, not just final answers. |
| Multimodal source registry | Keep source coordinates, pages, drawing zones, image regions, and extracted values tied together. |
| Repair/event hooks | Trigger repair when a handoff is missing, a branch changes silently, or source evidence conflicts. |

## Multimodal Extension Ladder

Do multimodality in layers. The verifier must know what counts as evidence before the source type becomes part of the benchmark.

| Layer | Source types | Verifier requirement | Good first products |
| --- | --- | --- | --- |
| Text/table | Schedules, datasheets, criteria tables, test records. | Exact cell/value provenance and unit checks. | Pump station, fire water, PV storage. |
| Drawing/plan | Plans, sections, elevations, schematics. | Page/zone references, extracted dimensions, topology checks. | Stormwater, facade, retaining wall, rail. |
| Image/photo | Sighting photos, equipment plates, site photos. | Region evidence, calibration assumptions, ambiguity records. | Rail signalling, pump curves, facade fixings. |
| Spatial/model | GIS, BIM, corridor strings, hydraulic models. | Object identity, coordinate frame, chainage, datum, and topology checks. | Road/rail, stormwater, retaining wall. |
| Dynamic/time series | Load profiles, rainfall hyetographs, process samples, protection curves. | Temporal alignment, scenario selection, and aggregation checks. | PV/BESS, treatment process, arc flash. |

## Meta-Harness Opportunities

Each composite template should compile into a meta-harness-manipulable task world:

| Operation | Product-level use |
| --- | --- |
| Projection | Strip to the source pack, stage graph, verifier gates, data gaps, or handoff chain. |
| Product | Compose civil, ground, mechanical, electrical, and structural worlds through named handoffs. |
| Subset | Generate easier variants by limiting disciplines, sources, gates, or data gaps. |
| Difference | Compare product variants and expose missing gates, missing sources, or changed assumptions. |
| Repair | Trigger on missing handoff, source contradiction, silent branch change, or impossible downstream value. |
| Redesign | Ask the meta-harness to add a source artifact, split a stage, promote a hidden branch, or strengthen a gate. |

The practical meta-harness pass for a compiled composite template should answer:

- Which source artifacts can be removed while keeping the task solvable?
- Which handoff fields are essential, redundant, or ambiguous?
- Which branch decisions are hidden in prose and should become explicit state?
- Which gates are formula-closure checks versus engineering-meaning checks?
- Which products can compose through shared handoffs?
- Which data gaps block real project execution versus richer benchmark variation?

## Running The Current Substrate

List the composite templates:

```bash
uv run aec-bench --json task composite-template list
```

Materialize and verify one runnable example:

```bash
uv run aec-bench --json task composite-template materialize-example pump-station-duty-package --output /tmp/pump-station-duty-package
uv run aec-bench --json task composite-template verify-example /tmp/pump-station-duty-package
```

The current verifier is intentionally deterministic and narrow. It proves that package structure, source refs, handoffs, branch decisions, deliverables, and gate records are coherent. Real execution still needs stage-level task generation and source parsers, but those should remain extensions of the composite task-world template substrate.
