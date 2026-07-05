# ABOUTME: Maps the live built-in task catalogue into task-world expansion opportunities.
# ABOUTME: Anchors multimodal, composition, and meta-harness analysis artifacts for follow-up work.

# Task-World Opportunities

This folder is the working record for the task-by-task investigation of AEC-Bench's built-in templates.

The purpose is to make future task development concrete: each task should be inspectable as a small task-world with inputs, outputs, hidden assumptions, evidence requirements, multimodal extensions, composition paths, and meta-harness operations.

## Artifact Map

| Artifact | Purpose |
| --- | --- |
| `methodology.md` | Shared review rubric used for every task card. |
| `task-catalogue.csv` | Machine-readable inventory of the live built-in templates. |
| `task-catalogue.md` | Human-readable catalogue grouped by discipline and category. |
| `task-cards/` | One first-pass card per template, generated from metadata and reviewed over time. |
| `detailed-passes/` | Meticulous grouped reviews covering every live template, with multimodal, combination, and meta-harness notes. |
| `combination-threads.md` | Cross-task workflow and product-world candidates. |
| `non-traditional-composition-threads.md` | Cross-discipline composition candidates that join worlds through shared evidence surfaces rather than only natural formula pipelines. |
| `shared-subworld-cluster-scan.md` | Exhaustive all-184 task-card scan that assigns each card to shared-subworld clusters and ranks clusters with the non-traditional composition rubric. |
| `shared-subworld-cluster-scan.csv` | Machine-readable ranked cluster table for the exhaustive shared-subworld scan. |
| `shared-subworld-card-membership.csv` | Per-card primary/secondary shared-subworld memberships keyed by task-card path. |
| `shared-subworld-designs/` | Detailed per-cluster long-horizon design pack for every shared-subworld scan world, including the SSC-20 authority overlay. |
| `shared-subworld-designs/design-manifest.csv` | Machine-readable coverage manifest for the detailed per-cluster design pack. |
| `ssc-17-energy-resilience-long-horizon-design.md` | Long-horizon product-world brainstorm for SSC-17 energy/resource/storage/resilience tasks, variants, shared-subworld manifest fields, and hardening order. |
| `meta-harness-threads.md` | Reusable meta-harness settings, operations, gates, and repair targets. |
| `long-horizon-task-research-report.md` | External benchmark and reward-design synthesis for long-horizon properties in composite task-world templates. |
| `long-horizon-methodology.md` | Composite task-world template boundary, construction loop, harness requirements, multimodal ladder, and meta-harness pass. |
| `long-horizon-product-benchmark.md` | Ten composite task-world templates with product-world scenarios, long-horizon challenges, multimodal paths, meta-harness hooks, and data gaps. |

## Current Scope

Live repository inspection on 2026-06-28 found `184` built-in template parameter files under `src/aec_bench/templates/builtin/`.

The current task surface is dominated by deterministic engineering calculation templates. That is useful: deterministic formulas make good closure gates, while the hidden-parameter and archetype machinery gives us a path toward richer scenario, document, drawing, image, table, and multi-step worlds.

Detailed pass coverage after the 2026-06-28 sweep:

| Discipline | Templates Covered | Detailed Passes |
| --- | ---: | ---: |
| Civil | 57 | 7 |
| Electrical | 52 | 5 |
| Ground | 10 | 1 |
| Mechanical | 50 | 4 |
| Structural | 15 | 1 |
| Total | 184 | 18 |

Use the detailed passes for task-by-task reasoning, then use `combination-threads.md`, `non-traditional-composition-threads.md`, `shared-subworld-cluster-scan.md`, `shared-subworld-designs/`, `ssc-17-energy-resilience-long-horizon-design.md`, and `meta-harness-threads.md` for cross-task product worlds, shared-subworld products, exhaustive all-card cluster selection, detailed cluster-specific long-horizon design, and reusable operation handles.
