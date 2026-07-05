# ABOUTME: Records the SSC-01-LH-07 review-first companion design before implementation.
# ABOUTME: Preserves the existing formula template while defining the source packet, variants, evidence, and verifier contract.

# SSC-01-LH-07 Review-First Design

This note applies the review-first authoring guide to `SSC-01-LH-07: Roadside Cabinet Flood, Heat, And Backup Energy Package`.

It preserves the existing formula-closure template, `roadside-cabinet-flood-heat-backup-energy-package`, as the math/source baseline. The additive review-first companion is `roadside-cabinet-serviceability-issue-review-package`. This design and implementation record does not replace the formula template, add model-run evidence, claim source-pack hardening, or claim benchmark readiness.

## Baseline To Preserve

Existing formula template:

```text
roadside-cabinet-flood-heat-backup-energy-package
```

Current shape:

```text
cabinet pad level and flood/inundation levels
  -> cabinet freeboard and flood margin
  -> enclosure heat derating and thermal margin
  -> battery runtime and BESS power/energy margins
  -> feeder voltage-drop margin
  -> road-lighting AECI
  -> synthetic pass score
```

That template is a useful saved calculation artifact. The review-first companion should not overwrite it. The companion should change the job from "calculate the cabinet resilience memo" to "review whether the roadside cabinet serviceability package is ready to issue."

## Review-First Companion

Human title:

```text
Review the roadside cabinet serviceability package for issue
```

Proposed template name:

```text
roadside-cabinet-serviceability-issue-review-package
```

Proposed directory:

```text
src/aec_bench/templates/builtin/electrical/roadside_cabinet_serviceability_issue_review_package/
```

Proposed category:

```text
road-review
```

The category stays aligned with the other SSC-01 review-first companions.

## Scene And Object IDs

Reuse the SSC-01-LH-07 object family so the review-first task remains connected to the formula baseline:

| Object | Suggested ID | Role |
| --- | --- | --- |
| Roadside cabinet | `CAB-SSC01-007` | Cabinet location, pad level, cable entry, enclosure, and issue package identity. |
| Flood/HGL event table | `HGL-SSC01-007` | HGL level, inundation level, controlling water level, and event case. |
| Heat derating note | `HEAT-SSC01-007` | Reference temperature, event temperature, derating rate, and enclosure capacity. |
| Critical load schedule | `LOAD-SSC01-007` | Cabinet critical load, lighting load, annual operating hours, and lit area. |
| Backup energy schedule | `BATT-SSC01-007` | Battery capacity, BESS inverter capacity, efficiency, and required autonomy. |
| Feeder/access note | `FEED-SSC01-007` | Feeder length, conductor resistance, voltage, power factor, voltage-drop limit, and maintenance access route. |
| Serviceability scenario | `OPS-SSC01-007` | Flood/heat/outage event case and cabinet serviceability basis. |
| Serviceability criteria memo | `MEMO-SSC01-007` | Minimum freeboard, thermal capacity rule, autonomy, voltage-drop, and AECI criteria. |
| Review comments | `CRIT-SSC01-007` | Review comments, boundary rules, and claim boundary. |

## Source Packet

The review-first task should generate eight source files under `/workspace/sources/`:

| File | Source role | Contents |
| --- | --- | --- |
| `document-register.md` | Register | Document IDs, revisions, status, discipline owner, and current/issued status. |
| `cabinet-setout-elevation.md` | Primary cabinet evidence | Cabinet ID, chainage, pad level, cable-entry note, serviceability scenario, and access object link. |
| `flood-inundation-table.md` | Flood evidence | HGL level, inundation level, controlling water level, minimum freeboard basis, and claimed flood margin. |
| `enclosure-derating-note.md` | Heat evidence | Reference temperature, event temperature, derating rate, enclosure capacity, and claimed thermal margin. |
| `critical-load-backup-schedule.md` | Load and backup evidence | Critical load, battery capacity, BESS inverter capacity, efficiency, required backup duration, and claimed backup margins. |
| `feeder-access-note.md` | Power/access evidence | Feeder length, conductor resistance, voltage, power factor, allowable voltage drop, access route state, lighting energy inputs, and claimed voltage-drop/AECI values. |
| `owner-serviceability-criterion.md` | Owner/operations criterion | Required event case, minimum freeboard, thermal capacity rule, backup autonomy, voltage-drop limit, lighting AECI check, and readiness rule. |
| `criteria-comments.md` | Criteria and review comments | Assessment bases, primary/collateral boundary rules, missing-data boundary rules, review comments, owners, and actions. |

Methods and conventions belong in `criteria-comments.md`, not the instruction. The instruction should only say that the packet is the source of truth.

## Review Matrix

Use the same nine review items:

| Item | SSC-01-LH-07 meaning |
| --- | --- |
| `RLR-01` | Packet completeness: all required cabinet setout, flood/HGL, heat derating, load/backup, feeder/access, owner-criterion, and criteria files are present with IDs and revisions. |
| `RLR-02` | Object identity: cabinet ID, chainage, flood/HGL event, heat event, critical load, backup schedule, feeder, and access note stay consistent. |
| `RLR-03` | Cabinet serviceability basis: flood freeboard, heat derating, backup runtime, and feeder voltage-drop basis are traceable, current, and recomputable. |
| `RLR-04` | Cabinet serviceability adequacy: flood freeboard and thermal derated capacity clear the source criteria for the same cabinet and event case. |
| `RLR-05` | Scenario consequence: the same flood/heat/outage event case is used across cabinet setout, HGL, heat derating, load, backup, feeder, access, and owner criterion. |
| `RLR-06` | Secondary power/access resilience: backup energy, BESS power, feeder voltage drop, maintenance access, and road-lighting AECI are source-backed and internally consistent with the selected cabinet load. |
| `RLR-07` | Comment and action closure: critical comments are closed or have named actions; minor comments may be carried with owner/action. |
| `RLR-08` | Readiness consistency: the final decision follows the review matrix, findings, information requests, and action register. |
| `RLR-09` | Claim boundary: the response avoids unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims. |

## Evidence Keys

Initial evidence keys for `compute()`:

| Key | Review role |
| --- | --- |
| `cabinet_freeboard_m` | RLR-03 flood freeboard recomputation. |
| `flood_freeboard_margin_m` | RLR-04 flood serviceability adequacy. |
| `thermal_derated_capacity_w` | RLR-03 heat-derating recomputation. |
| `thermal_margin_w` | RLR-04 thermal serviceability adequacy. |
| `thermal_utilization` | RLR-04 thermal load utilization. |
| `battery_runtime_h` | RLR-03/RLR-06 backup-runtime recomputation. |
| `battery_margin_h` | RLR-06 backup autonomy adequacy. |
| `bess_power_margin_kw` | RLR-06 BESS power adequacy. |
| `bess_energy_margin_kwh` | RLR-06 BESS energy adequacy. |
| `feeder_voltage_drop_percent` | RLR-03/RLR-06 feeder voltage-drop recomputation. |
| `voltage_drop_margin_percent` | RLR-06 voltage-drop adequacy. |
| `road_lighting_aeci_kwh_m2_y` | RLR-06 lighting energy indicator recomputation. |

The first implementation should use `thermal_capacity_deficient` as the primary RLR-04 genuine-failure route because it differentiates this task from the flood-freeboard emphasis already covered by SSC-01-LH-01. `flood_freeboard_deficient` remains a strong optional later route, but the first pass should avoid making LH07 a duplicate cabinet flood task.

## Variants

Use the eight-variant skeleton from the guide:

| Variant | Primary flip | Readiness | Required register behavior |
| --- | --- | --- | --- |
| `clean` | None | `ready_to_issue` | No findings, requests, or carried actions. |
| `missing_derating_rate` | `RLR-04 -> insufficient_data` | `not_ready_to_issue` | One information request naming the missing heat derating rate in `HEAT-SSC01-007`. |
| `stale_enclosure_derating_revision` | `RLR-03 -> fail` | `not_ready_to_issue` | One finding against the stale heat derating note / enclosure capacity basis. |
| `cabinet_event_mismatch` | `RLR-02 -> fail` | `not_ready_to_issue` | One finding where cabinet setout, flood/HGL, and heat/load sources do not refer to the same cabinet/event case. |
| `scenario_copy_forward` | `RLR-05 -> fail` | `not_ready_to_issue` | One finding where the flood/heat/outage event case is copied from another cabinet or corridor without a decision record. |
| `open_critical_comment` | `RLR-07 -> fail` | `not_ready_to_issue` | One finding for an open critical cabinet serviceability review comment without owner/action. |
| `minor_open_comment_carried` | None | `ready_with_carried_actions` | One carried action with owner and linked item. |
| `thermal_capacity_deficient` | `RLR-04 -> fail` | `not_ready_to_issue` | One finding where recomputed thermal derated capacity is below the critical load, while the package mis-claims adequacy. |

Optional later variant:

```text
flood_freeboard_deficient
```

Keep it out of the first implementation unless heat derating proves too narrow. One implementation pass should not include both `thermal_capacity_deficient` and `flood_freeboard_deficient` if that makes RLR-04 localization noisy.

## Boundary Rules

These rules should appear in the instruction, system prompt, and criteria source from the first implementation:

- Missing derating rate is an information-request case, not a known failed thermal-capacity calculation. Set RLR-04 to `insufficient_data`, omit `thermal_derated_capacity_w`, `thermal_margin_w`, and `thermal_utilization` if they cannot be computed from packet values, and request the exact missing derating rate/source.
- Missing derating rate is a critical blocker. The readiness decision should be `not_ready_to_issue`, not `ready_with_carried_actions`; do not carry the missing derating rate as a normal action.
- A copied flood/heat/outage event case belongs under RLR-05. Do not cascade it into RLR-02 if object IDs reconcile. Do not cascade it into RLR-03/RLR-04/RLR-06 when flood, heat, backup, BESS, feeder, access, and AECI evidence are source-backed and internally consistent with their stated source values.
- A stale enclosure derating note belongs under RLR-03. Do not also fail RLR-04 if the thermal adequacy checks are internally recomputable from current non-stale cabinet, load, event, and criteria sources.
- A cabinet/event mismatch belongs under RLR-02. Do not also fail flood freeboard, thermal capacity, backup, or feeder checks unless the mismatch independently makes those source values unrecomputable.
- Every finding, information request, and action must name one exact RLR item. Do not write combined items such as `RLR-04/RLR-06`.
- RLR-08 is reviewer self-consistency, not package-readiness positivity.

## Derivation-Controlled Quantities

The review-first engine should not reuse the fixed min/max values from the formula template. It should sample realistic ranges and derive pass/fail margins:

- Quantize levels to `0.01 m`.
- Quantize temperatures to `0.1 C`.
- Quantize derating rates to `0.01 percent per C`.
- Quantize loads and capacities to `5 W` or `10 W`.
- Quantize battery capacity to `0.1 kWh`, runtime to `0.1 h`, and BESS power to `0.1 kW`.
- Quantize feeder length to `0.01 km`, resistance to `0.01 ohm/km`, voltage to whole volts, and voltage-drop margins to `0.1 percent`.
- Quantize road-lighting power to `10 W`, annual hours to `10 h/y`, and lit area to `10 m2`.

Derive these quantities from hidden margins:

- `controlling_water_level_m = max(hgl_level_m, inundation_level_m)`.
- `cabinet_pad_level_m = controlling_water_level_m + minimum_freeboard_m + flood_freeboard_margin_m` for pass variants.
- For optional `flood_freeboard_deficient`, derive `cabinet_pad_level_m = controlling_water_level_m + minimum_freeboard_m - flood_freeboard_deficit_m`.
- `thermal_derated_capacity_w = enclosure_capacity_w_at_reference_temp * (1 - derate_pct_per_c / 100 * (event_temperature_c - reference_temperature_c))`.
- For pass variants, derive `critical_load_w = floor_to(thermal_derated_capacity_w - thermal_margin_target_w, 5 W)`.
- For `thermal_capacity_deficient`, derive `critical_load_w = ceil_to(thermal_derated_capacity_w + thermal_deficit_w, 5 W)` so `thermal_margin_w` is negative after printed-value recomputation.
- Derive `battery_capacity_kwh = ceil_to((required_backup_h + battery_runtime_margin_h) * critical_load_w / 1000 / battery_efficiency, 0.1 kWh)` so backup still passes even when the thermal check fails.
- Derive `bess_inverter_capacity_kw = ceil_to(critical_load_w / 1000 + bess_power_margin_kw, 0.1 kW)`.
- Derive `allowable_voltage_drop_pct = ceil_to(feeder_voltage_drop_percent + voltage_drop_margin_percent, 0.1 percent)`.
- Derive lighting AECI from printed lighting power, annual hours, and lit area; keep it as a secondary evidence key unless an owner AECI limit is explicitly included.

The criteria source must state all unit conventions explicitly, including controlling water level as the greater of HGL and inundation level, cabinet freeboard as pad level minus controlling water level, heat derating as reference capacity times the event-temperature derating factor, battery runtime as kWh times efficiency divided by load kW, BESS energy margin as usable battery energy minus required load energy, feeder voltage drop as `2 x length x resistance x current / voltage x 100`, and road-lighting AECI as annual lighting energy divided by lit area. Do not leave conversion conventions implicit.

## Verifier Implications

Start from the existing custom verifier pattern and adapt only constants:

```text
ITEM_EVIDENCE = {
  "RLR-03": ["cabinet_freeboard_m", "thermal_derated_capacity_w", "battery_runtime_h", "feeder_voltage_drop_percent"],
  "RLR-04": ["flood_freeboard_margin_m", "thermal_margin_w", "thermal_utilization"],
  "RLR-06": ["battery_margin_h", "bess_power_margin_kw", "bess_energy_margin_kwh", "voltage_drop_margin_percent", "road_lighting_aeci_kwh_m2_y"],
}
```

Use `VARIANT_REQUEST_TOKENS` for `missing_derating_rate`:

```text
("derating", "rate", "heat-ssc01-007")
```

Use `REQUIRED_LEDGER_TOKENS`:

```text
cab-ssc01-007, hgl-ssc01-007, heat-ssc01-007, load-ssc01-007, batt-ssc01-007, feed-ssc01-007, ops-ssc01-007, memo-ssc01-007
```

## TDD Implementation Slice

The first implementation should start with tests, not code:

1. Add `tests/templates/test_roadside_cabinet_serviceability_issue_review_package.py` before creating the template; the initial red state should be the missing template directory.
2. Preserve `roadside-cabinet-flood-heat-backup-energy-package` unchanged as the formula/source baseline.
3. Assert `tool_mode = "no-tool"`, eight source files under `environment/sources/`, no generated calc script, and no engineering numbers in `instruction.md`.
4. Assert all eight variants map to exactly one primary RLR flip, with `missing_derating_rate` producing RLR-04 `insufficient_data` and `thermal_capacity_deficient` producing RLR-04 `fail`.
5. Add closure tests that reparse rendered sources and independently recompute cabinet freeboard, flood margin, thermal derating, battery runtime, BESS margins, feeder voltage drop, and lighting AECI.
6. Add source-boundary tests for copied scenario, cabinet/event mismatch, stale enclosure derating note, and missing derating rate before running models.
7. Only after focused tests, generated instance validation, and Ara capture should this be added to the composite catalogue.

## Implementation Outcome

`roadside-cabinet-serviceability-issue-review-package` is now implemented as an additive no-tool built-in template under:

```text
src/aec_bench/templates/builtin/electrical/roadside_cabinet_serviceability_issue_review_package/
```

Implementation artifacts:

- `params.toml`: variable sampled parameters, eight packet variants, archetypes, difficulty presets, and review/evidence outputs.
- `engine.py`: source-pack rendering, quantized derivations, localized variant gold states, and golden pass/fail fixtures.
- `instruction.md` and `system_prompt.md`: source-packet review workflow, RLR matrix, missing-derating boundary, primary/collateral boundary, exact evidence keys, and claim boundary.
- `verify.py`: custom matrix/evidence/linkage/readiness/identity-claims verifier.
- `tests/templates/test_roadside_cabinet_serviceability_issue_review_package.py`: focused TDD coverage for discovery, baseline preservation, parameter variation, variant gold states, source-pack IDs, missing-derating boundary, source-owned methods, source-only recomputation, scaffold layout, golden fixtures, verifier localization, evidence gating, and readiness anti-gaming.
- `src/aec_bench/task_world_templates/catalogue.py` and `tests/task_world_templates/test_products.py`: composite-catalogue entry and tests preserving `roadside-cabinet-flood-heat-backup-energy-package` as the formula/source reference.

Validation captured in `ara/evidence/logs/ssc01_lh07_review_first_companion_self_check.txt`:

```text
uv run pytest tests/templates/test_roadside_cabinet_serviceability_issue_review_package.py -q
36 failed, 1 passed
```

The initial red state was the expected missing template directory.

```text
uv run pytest tests/templates/test_roadside_cabinet_serviceability_issue_review_package.py -q
37 passed
```

```text
uv run pytest tests/templates/test_roadside_cabinet_serviceability_issue_review_package.py tests/task_world_templates/test_products.py tests/templates/test_registry.py tests/generation/test_scaffolder_hooks.py -q
71 passed
```

```text
uv run aec-bench generate task roadside-cabinet-serviceability-issue-review-package --instances 8 --difficulty medium --seed 20260705 --output /private/tmp/aec-bench-ssc01-lh07-review-first-e2e
8 generated instances
```

The generated batch covered five variants: `thermal_capacity_deficient`, `missing_derating_rate`, `scenario_copy_forward`, `cabinet_event_mismatch`, and `clean`. The `stale_enclosure_derating_revision`, `open_critical_comment`, and `minor_open_comment_carried` variants are covered by focused tests but were not sampled in that seed batch.

All 8 generated instances validated with golden pass `1.000`, fluent-unsafe fail between `0.320` and `0.400`, and zero warnings.

```text
uv run aec-bench --json task composite-template materialize-example roadside-cabinet-serviceability-issue-review-package --output /private/tmp/aec-bench-ssc01-lh07-issue-review-composite-example
overall: pass, score: 1.0, data_gap_count: 5
```

```text
uv run aec-bench --json task composite-template verify-example /private/tmp/aec-bench-ssc01-lh07-issue-review-composite-example
overall: pass, score: 1.0
```

## Targeted Model Probe And Prompt Contract Delta

Two targeted Haiku probes were run through the Bedrock-backed `pydantic_ai` adapter on the `missing_derating_rate` variant:

- Pre-clarification run: `/private/tmp/aec-bench-ssc01-lh07-haiku-missing-derating-probe`, reward `0.83`. The model read the packet, computed the available evidence, identified the missing derating rate, and made a `not_ready_to_issue` decision, but it also marked `RLR-03` and `RLR-08` as failures. That exposed an ambiguity in the task contract: `RLR-03` asked whether the heat basis was recomputable, while the gold contract intended missing derating rate to localize to `RLR-04` as `insufficient_data`.
- After clarifying the missing-derating boundary in `instruction.md` and `system_prompt.md`: `/private/tmp/aec-bench-ssc01-lh07-haiku-missing-derating-prompt-boundary-probe`, reward `0.95`. The model received full matrix, evidence, linkage, readiness, and claim-boundary credit. The only remaining loss was strict identity-ledger credit because the schema did not explicitly say that `criteria_memo` must mention both `MEMO-SSC01-007` and `CRIT-SSC01-007`.
- After clarifying the `criteria_memo` MEMO/CRIT requirement: `/private/tmp/aec-bench-ssc01-lh07-haiku-missing-derating-current-prompt-probe`, reward `0.95`. The model now included both `MEMO-SSC01-007` and `CRIT-SSC01-007`; the remaining identity-ledger loss was that `serviceability_scenario` described the event but omitted the owner criterion ID `OPS-SSC01-007`.
- After clarifying the `serviceability_scenario` OPS requirement: `/private/tmp/aec-bench-ssc01-lh07-haiku-missing-derating-current-prompt-v2-probe`, reward `1.00`. The model received full matrix, evidence, linkage, readiness, identity-ledger, and claim-boundary credit.

Two targeted Haiku probes were then run on the `thermal_capacity_deficient` variant:

- Pre-thermal-convention hardening: `/private/tmp/aec-bench-ssc01-lh07-haiku-thermal-deficient-current-prompt-v2-probe`, reward `0.87`. The model correctly identified the known RLR-04 thermal adequacy failure, raised a finding, action, and `not_ready_to_issue` decision. It lost credit because `thermal_utilization` was emitted as percent `118.58` instead of ratio `1.1858`, and because it marked `RLR-08` fail even though its evidence said the not-ready decision reconciled with the failed RLR-04 state.
- After clarifying the thermal-utilization and RLR-08 boundaries in prompt text and source-owned criteria: `/private/tmp/aec-bench-ssc01-lh07-haiku-thermal-deficient-current-prompt-v3-probe`, reward `1.00`. The model received full matrix, evidence including `thermal_utilization`, linkage, readiness, identity-ledger, and claim-boundary credit.

One targeted Sonnet probe was then run on the same `thermal_capacity_deficient` instance:

- Sonnet current-prompt-v3 run: `/private/tmp/aec-bench-ssc01-lh07-sonnet-thermal-deficient-current-prompt-v3-probe`, original reward `0.95`. All matrix, evidence, linkage, readiness, and identity-ledger checks passed. The only loss was claim-boundary credit because the model wrote an explicit non-claim as "does not constitute" rather than the verifier's literal "does not claim" phrase.
- After tightening the verifier to accept explicit non-claim wording while still requiring the core boundary categories, the same Sonnet output rescored to `1.00` under `/private/tmp/aec-bench-ssc01-lh07-sonnet-thermal-deficient-current-prompt-v4-rescore`.

The current template now guards these prompt boundaries:

- Missing derating rate belongs under `RLR-04` only; do not fail `RLR-03` for that missing value when the heat note is current, and do not fail `RLR-08` merely because the reconciled decision is `not_ready_to_issue`.
- `identity_ledger.criteria_memo` must mention both `MEMO-SSC01-007` and `CRIT-SSC01-007`.
- `identity_ledger.serviceability_scenario` must mention `OPS-SSC01-007`.
- `RLR-08` passes when the readiness decision reconciles with the matrix, findings, information requests, and action register, even when the package is `not_ready_to_issue`.
- `thermal_utilization` is a ratio, not a percent.

The focused template test file now has 39 passing tests after adding prompt-contract and verifier-boundary guards. The current-prompt-v4 generated batch under `/private/tmp/aec-bench-ssc01-lh07-review-first-e2e-current-prompt-v4` includes the clarified instruction, system prompt, source-owned criteria memo, and claim-boundary verifier normalization. The `peri-urban-lighting-cabinet-suburban-field-cabinet-00` thermal-deficiency instance validates with golden pass `1.000`, fluent-unsafe fail `0.350`, and zero warnings.

This is useful diagnostic model-run evidence and contract hardening for two Haiku variants plus one Sonnet thermal-deficiency probe. It is not broad two-model evidence across the full variant distribution, source-pack hardening, generated benchmark readiness, or benchmark readiness.

## Non-Claims

This is a design and runnable synthetic implementation record for a task-owned review-first companion with targeted Haiku diagnostic probes on two variants and one Sonnet thermal-deficiency probe. It does not claim broad model-run evidence, real cabinet/enclosure/manufacturer/export parsing, accepted project evidence, authority approval, source-pack hardening, full standards compliance, generated benchmark readiness, or benchmark readiness.
