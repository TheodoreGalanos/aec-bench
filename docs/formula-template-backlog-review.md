# Formula Template Backlog Review

This review records the structural and mechanical seed triage performed for the
formula-template backlog. The working contract was intentionally narrow:
templates must be deterministic, closed-form, numeric or categorical on input,
numeric on output, and implementable as a single pure `compute()` function.

## Implemented in This Batch

The batch adds 65 built-in templates: 50 mechanical and 15 structural.

### Mechanical

- `air-changes`
- `air-demand`
- `a-weighting`
- `available-flow-calculation`
- `biogas-production`
- `braking-distance`
- `chemical-dosing`
- `cstr-volume`
- `davis-resistance`
- `distance-attenuation`
- `egress-width`
- `elevation-pressure`
- `friction-loss-hazen-williams`
- `gas-load-calculation`
- `gci-calculation`
- `hazen-williams-friction`
- `hrt-calculation`
- `lmtd-calculation`
- `mass-balance`
- `mlss-inventory`
- `minor-losses-calculation`
- `miner-fatigue`
- `nac-load-calculation`
- `nitrification-srt`
- `npsh-available`
- `occupant-load`
- `oxygen-requirements`
- `pfr-volume`
- `por-aor-compliance`
- `pressure-loss-calculation`
- `pump-affinity-laws`
- `pump-head-calculation`
- `pump-power-calculation`
- `pump-power-efficiency`
- `sabine-rt60`
- `slr-calculation`
- `sludge-production`
- `sor-calculation`
- `spl-log-sum`
- `sprinkler-discharge`
- `srt-calculation`
- `steel-critical-temp`
- `t-squared-hrr`
- `thrust-force-calculation`
- `joukowsky-pressure`
- `velocity-check`
- `vibration-transmissibility`
- `visibility-criterion`
- `wave-speed-calculation`
- `water-supply-curve`

### Structural

- `berthing-energy-calc`
- `bracket-load-calc`
- `carbon-equivalent-calc`
- `composite-section`
- `construction-tolerance`
- `effective-wind-area`
- `fender-energy-check`
- `gravity-base-stability`
- `lap-splice-length`
- `load-combinations`
- `mooring-line-capacity`
- `pipe-support-dead-load`
- `scm-substitution`
- `target-strength-calc`
- `thermal-movement-calc`

## Selection Rationale

These seeds were good candidates because their engineering method can be made
explicit in the template prompt and engine without relying on hidden standards
tables, model interpretation, drawings, document review, or iterative solving.

Typical accepted shapes were:

- First-principles physics, such as `delta L = alpha L delta T`.
- Direct hydraulic or process mass balances, such as `HRT = V/Q`.
- Explicit coefficient products, such as fender capacity corrections.
- Explicit stoichiometric factors, such as activated-sludge oxygen demand.
- Reduced first-order reactor sizing formulas, where the reaction order and
  rate law are part of the template contract rather than inferred.
- Reduced design checks where all governing criteria or load factors are
  explicit prompt inputs rather than inferred from a code standard.

## Rejected or Deferred Shapes

The following task shapes should not be converted mechanically without an
explicit reduced contract:

- QA, drawing, schedule, or document review tasks.
- FEM, network solve, root-finding, or time-series convergence tasks.
- Tasks whose natural answer is categorical only, unless a numeric surrogate is
  explicitly part of the benchmark contract.
- Tasks that require code-table lookups unless the table is embedded as a
  stable template constant and the prompt makes the lookup path explicit.
- Design checks where the seed names a broad code workflow but does not define
  the reduced formula, section properties, factors, or governing assumptions.

Examples deferred on this basis include:

- `sprinkler-hydraulics/hydraulic-calculation-full` because it is a network
  hydraulic solve.
- `system-curves/operating-point-determination` because it requires finding a
  pump/system curve intersection.
- `convergence-assessment/qoi-stability` because it depends on time-series or
  iteration-history data.
- `gas-services/gas-pipe-sizing` because it is primarily a standards table
  selection workflow.
- `process-deliverables/hmb-generation` because it is a report/data aggregation
  task rather than a single numeric computation.
- `wind-load-analysis/wind-pressure-calc` because it needs explicit code
  pressure coefficients, zones, and enclosure assumptions before templating.
- `load-analysis/live-load-distribution` because bridge distribution factors
  need a defined code formula set and girder class contract.
- `sanitary-drainage/self-cleansing-velocity` because partial-flow depth and
  pipe hydraulics need either an iterative solution or an explicit simplified
  full-flow contract.
- `chlorine-ct-calculation` because required CT values come from tables unless
  those tables are deliberately embedded.

## Validation Evidence

The implemented batch was validated with:

- Template registry discovery: 144 built-in templates found.
- `uv run pytest tests/templates`: 262 tests passing.
- `uv run ruff check src/aec_bench/templates/builtin/mechanical src/aec_bench/templates/builtin/structural tests/templates/test_formula_template_backlog_engines.py`
- `uv run ruff format --check src/aec_bench/templates/builtin/mechanical src/aec_bench/templates/builtin/structural tests/templates/test_formula_template_backlog_engines.py`
- Easy, medium, and hard instance generation for each implemented template,
  including live generation to `/private/tmp/aec-bench-formula-generated` for
  the second tranche.

## Completion Audit

The concrete deliverables for this batch were:

- Review the untouched structural and mechanical seeds against the formula
  template contract.
- Select good candidates and reject or defer seeds that violate the contract.
- Add built-in templates with `engine.py`, `params.toml`, `instruction.md`,
  and package markers.
- Add instance-generation scaffolding through the existing template generator,
  not a manual task copy.
- Add focused tests that prove registry loading and known formula outputs.
- Validate discovery, generation, linting, formatting, and template tests.

Current evidence:

- `find tasks/structural tasks/mechanical -name source_task.json -maxdepth 4`
  found 226 structural/mechanical seeds to review as the working backlog pool.
- `find src/aec_bench/templates/builtin/mechanical src/aec_bench/templates/builtin/structural -maxdepth 2 -name params.toml`
  found 65 new built-in templates in this branch.
- Registry discovery returns 144 built-in templates and all 65 new template
  names are present.
- `tests/templates/test_formula_template_backlog_engines.py` contains formula
  checks for all 65 new engines and registry loading checks for all 65 template
  directories.
- `uv run pytest tests/templates` passes 262 tests.
- `uv run ruff check ...` and `uv run ruff format --check ...` pass for the
  new mechanical/structural template trees and focused test file.
- ASCII checks pass for the new docs, template files, and focused tests.

Follow-on source-task tranche validation:

- Added 40 built-in templates from seed-only `source_task.json` entries:
  `tidal-prism`, `line-inductance`, `pfc-sizing`, `ppm-calculation`, and
  `yellow-interval-calculation`, plus `4-20ma-scaling`,
  `fiber-link-loss-budget`, `bandwidth-calculation`,
  `cctv-storage-calculation`, `pedestrian-clearance-time`,
  `poe-power-budget`, `power-load-calculation`, `rf-link-budget`,
  `warning-time-calculation`, `vms-legibility-distance`, `line-capacitance`,
  `voltage-regulation`, `radial-feeder-voltage-drop`,
  `signal-sighting-distance`, `battery-sizing`,
  `all-red-interval-calculation`, `interval-calculation`,
  `handling-capacity`, `escalator-capacity`, and
  `conduit-fill-calculation`, plus `road-pdi-calculation`,
  `road-aeci-calculation`, `leni-calculation`, `road-uniformity-check`, and
  `interior-uniformity`, plus `bess-sizing-basic`, `wind-load-conductor`,
  `ice-load-calculation`, `overlap-calculation`, and `voltage-drop-dc`.
  The latest tranche also adds `lux-level-calculation`,
  `sports-illuminance-uniformity`, `shaft-dimensions`,
  `car-dimensions-check`, and `access-controller-sizing`.
- Template registry discovery after the tranche: 184 built-in templates found.
- `uv run pytest tests/templates/test_source_task_formula_tranche.py` passes 41
  tests after the latest source-task tranche.
- `uv run pytest tests/templates` passes 307 tests.
- `uv run ruff check ...` and `uv run ruff format --check ...` pass for the
  new template directories and focused test file.
- `uv run aec-bench generate validate-template ...` passes for all 30 new
  template directories.
- Easy, medium, and hard preview generation succeeded for each new template at
  `/private/tmp/aec-bench-source-task-tranche` and
  `/private/tmp/aec-bench-source-task-lighting`, and
  `/private/tmp/aec-bench-source-task-utility`, and
  `/private/tmp/aec-bench-source-task-building`.

Residual gap:

- The strong closed-form structural/mechanical candidates identified in this
  review have been converted. The wider seed backlog is not exhausted; further
  conversion should continue only after a reduced deterministic contract is
  agreed for table-driven, categorical, iterative, or design-code-heavy seeds.
- A broad `source_task.json` audit now finds 282 unique task-id gaps after the
  current built-in template names are matched against source-task ids.

## Next Good Candidates

The next tranche should be designed before implementation rather than generated
blindly. Good candidates if the reduced contract is agreed:

- Fixed-shape `srt` and wastewater process variants beyond the current mass
  balance set.
- Structural member checks where section properties, capacity factors, and
  formula scope are explicit inputs.
- Load-combination templates where every load factor is an explicit input and
  the output uses numeric governing utilisation or governing-combination index.
- Pipe and duct sizing templates where the method is fixed to a non-iterative
  form or the candidate diameter set is embedded as a stable lookup table.
