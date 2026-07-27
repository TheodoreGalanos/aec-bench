# ABOUTME: Plans ASW-0B4's bounded synthetic family, generator, independent certification, and promotion protocol.
# ABOUTME: Preserves research and production boundaries while decomposing B4 into focused, sequential review slices.

# ASW-0B4 — Generator and certification protocol plan

## 1. Plan identity

| Field | Value |
| --- | --- |
| Programme stage being planned | `ASW-0B4 — Generator and certification protocol` |
| Planning status | Draft for review; does not accept or complete ASW-0B4 |
| Repository baseline | `6be850c6204ae9aea193309a2c8f3df639ece928` |
| Parent PRD SHA-256 | `56d6fe6a9c69796d819a1995ae63a85392ba85a4240df8baa87df99a76678335` |
| B1 claim/profile SHA-256 | `1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954` |
| B2 evidence/rights SHA-256 | `8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96` |
| B3 engine-role decision SHA-256 | `90603ddd481c0b627ad5e8ae5e0fc45f4c73b3910c86a8038cd80ce8eb80303d` |
| B3 compact verification SHA-256 | `db93443b31a197864709e7011af8a6aa15932cbec3260cf1a2afed735ffa3f11` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Next stage that this plan may eventually open | `ASW-0B5 — V3 world-family certification` only |

The identities above bind this plan to the accepted predecessor evidence. If
any predecessor bytes or semantic decisions change, B4 stops until the impact
is reviewed and the binding is updated deliberately.

### 1.1 Relationship to the parent PRD

This file is a subordinate execution plan for the existing ASW-0B4 roadmap
entry. It adds traceability, decision order, review packages, and exit evidence;
it does not amend the programme stages, authority allocation, claim boundary,
or acceptance gates.

The authority order is:

1. `asset-stewardship-worlds-prd.md`;
2. the accepted B1 claim/profile;
3. the accepted B2 evidence/rights pack;
4. the accepted B3 engine-role decision and verification record; and
5. this B4 execution plan.

If this plan conflicts with a higher authority, the plan is invalid at that
point and must be corrected or the higher authority must be amended through a
separate explicit review. Silence, greater detail, or later authorship does not
allow this plan to override a predecessor.

| Higher-authority ruling | Binding treatment in this plan |
| --- | --- |
| ASW-0B4 specifies the family, generator, certifier, sensitivities, tolerances, stop rules, and promotion-manifest shape | Sections 6–17 decompose those decisions without generating a member |
| ASW-0B5 generates, independently certifies, rejects, and promotes the family | B5 execution and every V-level pass remain explicit B4 non-outcomes |
| ASW-0C owns exact histories, scenario timing, treatments, endpoints, and research claims | B4 freezes only physical predicates and parameterized consequences |
| ASW-1 owns action authority, obligations, host boundaries, persistence, visibility contracts, and staged promotion design | B4 uses conceptual exchanges and creates no importable or persisted contract |
| ASW-2 owns runtime implementation and integration | No file under `src/aec_bench` is allowed in B4 |
| B3 selects SWMM only as an offline generator candidate and keeps certification separate | Sections 10–11 preserve the asymmetric role boundary |
| B2 accepts mechanism forms and contextual sources but no parameter transfer | B4-W1 must construct original values and return to B2 when evidence is insufficient |
| The first profile remains one asset, Pump A/Pump B, and one A-to-B transfer | The parameter and generator protocols reject broader topology and simultaneous pumping |
| V3 requires AG-01 through AG-13 and independent certification | Section 17 maps B4 protocol obligations to future B5 evidence without marking a gate passed |
| Research artifacts are evidence, not runtime authority | Sections 14–16 require content-based promotion and research-path absence |

## 2. Purpose

ASW-0B4 must turn the frozen fictional duty/standby profile and the accepted
SWMM role decision into a complete, reviewable protocol from which two
separately executable research implementations can be built:

1. an offline generator that uses pinned SWMM to produce candidate hydraulic
   consequences; and
2. an independent certifier that can accept or reject those candidates without
   calling or trusting the generator's claim-critical decision path.

B4 ends when B5 can implement, execute, reject, reproduce, and promote a small
world family without inventing an unstated parameter, equation, tolerance,
visibility rule, rights decision, or acceptance criterion.

B4 does not generate or promote a world. It specifies how B5 will do so.

## 3. Outcomes and non-outcomes

### 3.1 Required outcomes

B4 must freeze:

- one original, bounded synthetic parameter family with units, derivations,
  assumptions, source classes, rights treatment, and operating envelope;
- one primary and one secondary physical mechanism, including applicability,
  latent-state progression, hydraulic effect, intervention effect, and
  falsification conditions;
- the physical trigger and consequence of the single permitted Pump A to Pump
  B duty transfer, without selecting scenario timing or institutional
  authority;
- separate calendar, runtime, and start-count clocks and their exact counting
  rules;
- the distinction between latent truth and observable evidence;
- SWMM generator inputs, configuration, allowed outputs, warnings, and failure
  behavior;
- the independent certifier's equations, reference cases, invariants, units,
  tolerances, and prohibited dependencies;
- a preregistered deterministic sensitivity design and rejection rules;
- content-addressed lineage and receipt requirements;
- a research-side promotion-manifest specification for one exact B5
  generation; and
- the conditions under which B3 research machinery is later retired from the
  repository's current tree.

### 3.2 Explicit non-outcomes

B4 must not:

- generate a candidate world-family member;
- claim V0, V1, V2, V3, empirical calibration, regional representativeness,
  compliance, operational suitability, or digital-twin status;
- select scenario dates, event timing, actor authority, obligation wording,
  treatment conditions, study endpoints, or model budgets;
- create asset runtime, state-machine, task-verifier, harness, provider,
  evaluation, persistence, CLI, Harbor, `TrialRecord`, or public registry code;
- create or export a global contract;
- import production code from `research/`;
- copy B3 fixture values, numerical tolerances, file layouts, Python names, or
  generated inputs as B4 authority;
- copy the external research prototype's fixed `0.72` obstruction transform,
  parameter set, case definitions, or checker tolerances;
- expose raw SWMM, latent state, sealed certification cases, future events, or
  evaluator targets to an agent;
- use SWMM or its output wrapper as its own independent certifier; or
- make paths under research, temporary, build, run, or staging directories into
  identifiers or compatibility promises.

## 4. Planning-slice boundary

This planning slice is deliberately smaller than B4 execution.

### 4.1 Allowed files

- `.gitignore`
- `research/asset-stewardship/asw-0b4-generator-and-certification-plan.md`

### 4.2 Forbidden files and surfaces

- every file under `src/aec_bench`;
- tests for production packages, contracts, CLI, Harbor, providers, harness,
  evaluation, or task registries;
- the accepted B3 spike and its compact evidence;
- predecessor B1, B2, and B3 authorities;
- normative repository architecture documents; and
- generated solver inputs, outputs, reports, binaries, source trees, build
  receipts, or candidate world packages.

This plan is a durable programme authority, not executable research and not a
runtime ABI. Later B4 execution slices require their own exact allowlists.

## 5. Fixed predecessor rulings

The following decisions are inputs, not open design space:

1. The profile is original and fictional, with one pump set and exactly Pump A
   and Pump B.
2. Pump A starts as duty and Pump B as standby.
3. The first vertical slice permits one canonical A-to-B duty transfer, with no
   periodic alternation, simultaneous load sharing, fleet optimization, or
   adaptive duty selection.
4. The family is deterministic and synthetic. No real failure rate, remaining
   useful life, manufacturer performance, or population claim is permitted.
5. SWMM 5.2.4 at commit
   `7952ca837988b1c32f791812eccc9fd64547e093` is selected only for B4/B5
   offline generator protocol design.
6. The independent certifier remains a separate path.
7. The first runtime will consume a promoted deterministic package without
   SWMM or research dependencies.
8. Raw SWMM is not an agent-visible tool, and live-solver integration remains
   deferred.
9. V3 is required before ASW-2 production implementation begins; V4 is
   optional.
10. The eventual production package remains asset-local under
    `src/aec_bench/task_world_templates/`; B4 creates no production placement
    or import.

## 6. Open decision register

Every row must receive an explicit `accept`, `narrow`, `replace`, or `stop`
ruling during B4.

| ID | Decision | Current candidate or constraint | Required evidence |
| --- | --- | --- | --- |
| `B4-D01` | Original clean pump representation | Original synthetic monotone head-flow curve; no commercial pump curve | Derivation, dimensional review, bounded operating envelope, curve-shape checks |
| `B4-D02` | System and wet-well representation | Static head, force-main losses, cylindrical wet well, bounded inflow | N/P support, original geometry, units, mass balance, operating-point existence |
| `B4-D03` | Primary mechanism | Obstruction/ragging is the leading candidate | `N-004`/`P-003` applicability, original progression law, sensitivity robustness |
| `B4-D04` | Secondary mechanism | Hydraulic-clearance loss is conditional | `P-004` applicability to the declared synthetic configuration, or B2 amendment |
| `B4-D05` | Exposure mapping | Runtime and starts may advance mechanisms differently | Exact counting rules and evidence that the clocks are not redundant |
| `B4-D06` | Calendar-time role | Calendar advances independently during standby and constraints | Exact interaction with access, lead-time, observation, and no-maintenance progression |
| `B4-D07` | Transfer trigger | Capability or drawdown insufficiency is a candidate | Deterministic physical definition separated from scenario timing and authority |
| `B4-D08` | Transfer consequence | Pump B assumes duty while Pump A's latent state and history persist | Mass balance, exposure reassignment, no automatic history erasure |
| `B4-D09` | Observation model | Deterministic sensor/inspection channel distinct from latent truth | At least one informative and one ambiguous observation construction |
| `B4-D10` | Intervention effects | Inspection, obstruction clearance, and clearance-related repair candidates | Physical effect only; no operational recommendation or authority semantics |
| `B4-D11` | Resource constraint | Access/outage and a repair/spare lead-time candidate | Consequential but bounded semantics; exact scenario schedule deferred |
| `B4-D12` | Generator decomposition | SWMM trajectory generation versus certified semantic tables | Proof that the promoted package can later run without SWMM |
| `B4-D13` | Independent calculation path | Analytical/numerical implementation separate from SWMM wrapper | Dependency audit, reference cases, unit and residual checks |
| `B4-D14` | Numerical tolerances | Derived from resolution and method, not tuned to observed results | Preregistered absolute, relative, integral, and exact-check categories |
| `B4-D15` | Sensitivity region | Bounded deterministic perturbation grid | Source/assumption mapping and stable qualitative outcome ordering |
| `B4-D16` | Promotion contents | Minimum rights-cleared semantic package | Exact file/field allowlist and visibility classes |
| `B4-D17` | B3 retirement point | After B5 promotion and ASW-2A0 absence proof | Promotion identity, self-contained reader proof, dedicated removal review |

## 7. Proposed physical construction to test

This section records the starting hypothesis for B4 review. It does not select
values or accept mechanisms.

### 7.1 Hydraulic base

The proposed base is:

- one cylindrical wet well;
- one bounded deterministic inflow family;
- one original force-main/system representation;
- two label-symmetric synthetic pump trains;
- one original clean pump curve shared by Pump A and Pump B at initial state;
- a single-pump operating rule; and
- no network, catchment, electrical, controls, workforce, inventory, or
  enterprise work-management simulation beyond the minimum constraint
  surfaces required by the profile.

The clean operating point must be defined by the intersection of an original
pump curve and a system curve. Wet-well change must satisfy independent volume
balance. Hydraulic power may be derived for certification or observation only
when every required assumption and efficiency term is explicit.

### 7.2 Primary mechanism hypothesis

Obstruction/ragging is the preferred primary candidate because it is directly
credible in wastewater service, can affect head/flow/power in
operating-point-dependent ways, and can support an intervention whose physical
effect differs from passive deferral.

B4 must not infer a universal blockage multiplier or empirical failure rate.
It must construct an original bounded latent severity and transformation whose:

- progression is deterministic;
- driver clocks are explicit;
- effect cannot improve the declared clean capability envelope;
- effect is tested across the declared operating range;
- clearing behavior is separately specified;
- reasonable parameter perturbations do not reverse the intended qualitative
  consequence; and
- limitations are stated as synthetic assumptions rather than field claims.

### 7.3 Secondary mechanism hypothesis

Hydraulic-clearance loss is the preferred secondary candidate only if B4
declares a synthetic pump configuration for which the relevant clearance
surface is meaningful. It should provide a different persistence and
intervention signature from obstruction:

- it may progress under operating exposure;
- an obstruction-clearing intervention must not reset it;
- restoration may require a repair/spare/access path; and
- repair may restore capability while retaining exposure and intervention
  history.

If applicability cannot be established without importing an unsupported real
pump design, B4 stops this selection and returns to B2 for another mechanism.

### 7.4 Clock hypothesis

The minimum physical clock set is:

- simulated calendar time;
- per-pump accumulated operating time; and
- per-pump start count.

Standby time advances calendar time but not standby-pump runtime. Duty transfer
changes which pump receives later exposure without rewriting earlier exposure.
Counting at boundaries, simultaneous timestamp ordering, and clock precision
must be frozen before generation.

### 7.5 Transfer hypothesis

B4 must define a physical predicate for insufficient Pump A capability, such as
failure to satisfy a preregistered drawdown or hydraulic-margin condition. The
predicate is not an alarm standard or operational recommendation.

When a later scenario invokes the single permitted transfer:

- Pump B becomes the sole duty pump;
- Pump A stops accumulating operating exposure;
- both pumps retain latent condition and clock history;
- hydraulic consequences change according to the current pump states; and
- institutional authorization, obligation creation, and exact timing remain
  later-stage decisions.

### 7.6 Observation and intervention hypotheses

The observation channel must be deterministic and separate from latent truth.
Candidate observable families include bounded flow, level/drawdown, runtime,
starts, power, alarms derived from synthetic rules, and inspection findings.
The final set must be the minimum needed for the intended benchmark.

B4 must construct at least one same-reading/different-history pair: two states
with the same allowed current observation but different latent composition or
exposure history, producing a meaningful difference in future consequence or
required verification.

Physical intervention candidates are:

- inspection, which changes evidence but not latent physical state;
- obstruction clearing, which changes the obstruction state under a declared
  bounded effect;
- clearance-related repair, which changes the secondary mechanism under a
  declared bounded effect; and
- post-intervention verification operation, which generates new evidence
  without erasing history.

Exact action names, authority, work-order semantics, and obligations remain
outside B4.

## 8. B4 internal work packages

B4 should be executed through sequential, merged work packages rather than a
stacked branch. These labels are internal decomposition only; they do not add
or renumber PRD stages. No later work package opens until its predecessor is
accepted, and only completion of the whole ASW-0B4 gate may open ASW-0B5.

### B4-W0 — Plan and gate

**Scope:** this document and its exact ignore exception.

**Exit:**

- predecessor identities match;
- B4 scope, decisions, work order, boundaries, and stop conditions are
  reviewable;
- no production or executable research surface is created; and
- the first substantive slice is unambiguous.

### B4-W1 — Parameter family and mechanism rulings

**Scope:**

- define parameter groups, SI units, synthetic derivations, bounds, and
  cross-parameter constraints;
- decide the clean pump/system/wet-well/inflow construction;
- accept or reject obstruction as primary;
- establish or reject clearance-loss applicability as secondary;
- freeze latent-state variables, clock drivers, and intervention effects; and
- update the assumption, source, rights, unit, and decision registers.

**Required review artifact:** one mechanism-and-parameter-family authority with
no generated world member.

**Exit:** every parameter is derived or bounded without copying B3 values; both
mechanisms have falsifiable applicability and stop rules.

### B4-W2 — Generator protocol

**Scope:**

- define canonical research inputs and validation order;
- map only hydraulic responsibilities to pinned SWMM;
- freeze solver settings and their derivation;
- define generated case families and deterministic ordering;
- freeze the semantic output allowlist;
- define warning, convergence, period-count, units, and extraction failures;
- define replay and semantic hashing; and
- prove by design that raw solver files are not promotion candidates.

**Required review artifact:** one generator protocol and conceptual
input/output examples. Examples are explanatory, not importable schemas.

**Exit:** an implementer can build the generator without inventing physical or
serialization decisions.

### B4-W3 — Independent certification protocol

**Scope:**

- define a separately executable certifier boundary;
- define independent equations and numerical methods;
- disclose every common dependency;
- create analytical and limiting reference cases;
- freeze units, invariants, residuals, monotonicity checks, and label symmetry;
- define cross-checks for mass balance, operating points, clocks, transfer,
  observation ambiguity, and intervention effects; and
- prohibit imports from the generator or its SWMM wrapper.

**Required review artifact:** one certification protocol plus an independence
matrix.

**Exit:** the certifier can reject generator output without relying on a
generator assertion or a second wrapper around the same calculation.

### B4-W4 — Sensitivity, tolerance, and rejection protocol

**Scope:**

- classify exact, absolute, relative, integral, and qualitative checks;
- derive tolerances before running the family;
- freeze boundary and perturbation cases;
- define reasonable assumption ranges;
- identify assumption-fragile regions;
- preregister qualitative ordering requirements; and
- define generation-level and family-level rejection receipts.

**Required review artifact:** one preregistered sensitivity matrix and stop-rule
register.

**Exit:** B5 cannot tune tolerances after seeing candidate results, and fragile
members are rejected rather than rationalized.

### B4-W5 — Lineage and promotion protocol

**Scope:**

- freeze canonical research receipt requirements;
- define content identity independently of filesystem location;
- map inputs and derived values to evidence, rights, units, transformations,
  and assumptions;
- define public, agent-visible, host-private, certification-private, and
  holdout-sensitive visibility classes;
- define the research-side promotion-manifest specification;
- define unknown-field, unlisted-file, rights, hash, and version failures; and
- define B3 retirement evidence.

**Required review artifact:** one lineage and promotion protocol with a
conceptual manifest example.

**Exit:** B5 can issue one exact promotion manifest, while ASW-2A0 can later
implement a strict reader without importing B4/B5 research.

### B4-W6 — Adversarial protocol review and B4 decision

**Scope:**

- trace every B1/B2/B3 deferred decision to a B4 ruling;
- trace AG-01 through AG-13 to planned B5 evidence;
- run paper/reference cases through generator and certifier specifications;
- check that no hidden common implementation remains;
- check rights and visibility exclusions;
- check the protocol with research paths treated as non-authoritative;
- record unresolved risks and assumption-fragile regions; and
- issue `accept`, `repair`, `return to B2/B3`, or `abandon`.

**Exit:** only an accepted B4 decision opens B5.

## 9. Parameter-family protocol requirements

B4-W1 must define bounded groups rather than a bag of independent values:

| Group | Minimum contents | Required cross-check |
| --- | --- | --- |
| Geometry | Wet-well area/diameter, level bounds, static elevations, force-main length/diameter/roughness or equivalent | Positive dimensions, storage identity, valid engine envelope |
| Inflow | Deterministic base pattern and bounded family variation | Volume accounting, no hidden stochasticity, declared horizon |
| Clean pump | Original head-flow curve, allowed operating range, any efficiency/power assumptions | Monotonic shape, system intersection, no commercial-curve claim |
| Controls for generation | Single-duty activation/deactivation needed for hydraulic cases | No periodic alternation, load sharing, or runtime authority semantics |
| Primary mechanism | Latent obstruction state, progression driver, curve/effect transform, clearing effect | No capability improvement, bounded reversibility, sensitivity stability |
| Secondary mechanism | Latent clearance state, progression driver, hydraulic transform, repair effect | Applicability, distinct persistence, no reset by obstruction clearing |
| Clocks | Calendar, runtime, starts, precision, increment ordering | Standby/duty divergence, replay-stable boundary behavior |
| Observation | Allowlisted readings, resolution/bias/availability assumptions, inspection mapping | Latent/observable separation and paired-history ambiguity |
| Transfer physics | Capability predicate and post-transfer hydraulic ownership | One transfer maximum, no simultaneous pumping, history retained |
| Resources | Minimal access/outage/spare or lead-time parameters | Consequential without enterprise-system simulation |

Every value must carry:

- a stable parameter identity local to the research protocol;
- SI unit and dimensional type;
- source/evidence class;
- rights class;
- original value or derivation;
- lower and upper bound;
- cross-parameter constraints;
- sensitivity treatment;
- claim ceiling;
- visibility classification; and
- B5 rejection behavior.

The protocol may use original deterministic values. “Synthetic” does not mean
unbounded, unexplained, or exempt from dimensional and sensitivity review.

## 10. Generator protocol requirements

### 10.1 Authority

The generator owns candidate hydraulic consequence production only. It does not
own:

- certification;
- stewardship actions or authority;
- obligation creation or closure;
- institutional records;
- handover;
- scoring;
- visibility policy;
- promotion; or
- runtime truth.

### 10.2 Conceptual input classes

The generator protocol must define, without creating a production schema:

- protocol and profile identities;
- generation identity and deterministic case identity;
- parameter-family member;
- pump-label assignment;
- mechanism state and physical intervention schedule for the hydraulic case;
- simulation horizon and reporting/routing settings;
- semantic output request allowlist; and
- exact engine/build identities.

### 10.3 Semantic output allowlist

The minimum candidate set for B4 review is:

- time;
- wet-well depth and volume;
- inflow;
- Pump A and Pump B flow;
- force-main flow;
- flooding/overflow quantity;
- pump operational status;
- engine continuity/convergence diagnostics; and
- only those power or derived quantities for which assumptions are fully
  specified and independently checked.

Raw `.inp`, `.out`, `.rpt`, binary libraries, source trees, logs, and build
paths remain research-only. Report text is diagnostic evidence, not a replay
contract.

### 10.4 Fail-closed behavior

The generator must reject:

- wrong engine version, commit, executable, library, patch, or configuration;
- unknown inputs or output requests;
- invalid units, non-finite values, invalid curve shapes, or impossible bounds;
- absent or multiple operating-point intersections where one is required;
- unexpected periods, elements, warnings, errors, or convergence status;
- stale or reused workspaces;
- output path collisions;
- semantic-series shape drift; and
- any request outside the frozen B4 envelope.

## 11. Independent certification protocol

### 11.1 Separation rule

The certifier must run as a separate command/process and may consume only
canonical protocol inputs and allowlisted semantic candidate outputs. It must
not:

- import the generator package;
- call SWMM;
- call the SWMM output library;
- use the generator's pump/system intersection helper;
- trust generator pass/fail assertions;
- derive expected periods, units, or element identities from generated
  assertions alone; or
- award benchmark success or task reward.

Neutral serialization and SI definitions may be shared only when recorded as
common dependencies. Claim-critical equations cannot be shared.

### 11.2 Independent check families

The protocol must specify:

- dimensional and finite-value checks;
- wet-well volume balance;
- independently calculated system head;
- independently solved pump/system operating points;
- hydraulic power identities when power is included;
- clean, obstructed, and clearance-loss monotonicity/boundedness;
- Pump A/Pump B label symmetry;
- duty-only and standby-zero-flow behavior;
- exact clock accumulation;
- transfer conservation and exposure reassignment;
- no-maintenance consequence;
- intervention-specific state effects;
- non-erasure of unrelated latent state and history;
- latent/observable separation;
- same-reading/different-history construction;
- replay identity; and
- promotion-content and rights checks.

### 11.3 Reference cases

At minimum, B4 must preregister:

1. zero-inflow/static-storage boundary;
2. clean single-pump operating point;
3. label-swapped clean operating point;
4. bounded primary-mechanism progression;
5. bounded secondary-mechanism progression;
6. combined-mechanism case;
7. no-maintenance case;
8. obstruction-clearing case that leaves secondary state intact;
9. secondary repair case that retains clocks/history;
10. A-to-B transfer case;
11. same-reading/different-history pair; and
12. deliberately invalid cases proving certifier rejection.

These are protocol cases, not the later study history.

## 12. Tolerance and sensitivity policy

### 12.1 Tolerance classes

| Class | Intended use | Rule |
| --- | --- | --- |
| Exact | Identities, hashes, counts, labels, booleans, enum-like rulings | No numerical tolerance |
| Absolute | Near-zero flows, volume residuals, clock precision | Derived from discretization and representation |
| Relative | Non-zero operating points and hydraulic quantities | Denominator and zero behavior frozen in advance |
| Integral/cumulative | Mass balance, runtime, overflow, energy where included | Calculated across the full declared horizon |
| Qualitative | Monotonicity, action ordering, capability non-improvement | Any reversal in the preregistered region rejects the member |

Tolerances must be justified from numerical method, reporting resolution,
serialization precision, and independent reference-case behavior. They must not
be selected by observing what a candidate happens to pass.

### 12.2 Sensitivity classes

B4-W4 must include:

- lower/nominal/upper bounded parameter cases;
- boundary proximity cases;
- reporting and routing resolution perturbations;
- mechanism progression and intervention-effect perturbations;
- inflow and static-head envelope perturbations;
- observation resolution/bias perturbations;
- access/lead-time constraint perturbations; and
- combined cases selected to expose interactions without exploding the family.

The first family should use a small deterministic design, not an opaque random
search. If any seed is later used, it becomes a pinned input and never replaces
boundary cases.

### 12.3 Required stable qualitative orderings

Candidate orderings for B4 review include:

- clean capability is not worse than degraded capability under matched
  conditions;
- adding a mechanism cannot improve the declared capability envelope;
- no-maintenance progression has a meaningful adverse consequence;
- a physically applicable intervention improves its target mechanism relative
  to deferral;
- obstruction clearing does not repair clearance loss;
- repair does not erase clocks or historical events;
- loss or restriction of Pump A does not increase station capacity;
- label swap changes labels, not symmetric physical results; and
- post-transfer exposure accumulates on Pump B without rewriting Pump A's
  history.

Any ordering that cannot be defended before execution is narrowed or removed,
not silently tuned after generation.

## 13. Rejection, stop, and pivot rules

B4 or B5 must stop the affected design or generation when:

- a mechanism cannot be supported at the form/applicability level by accepted
  N, P, or E evidence;
- a value lacks source class, rights class, units, derivation, or assumption;
- cite-only or excluded bytes would enter a distributable artifact;
- no bounded operating point exists, or engine and independent calculations
  disagree outside preregistered tolerance;
- mass balance, monotonicity, clock, symmetry, or intervention invariants fail;
- the intended qualitative ordering reverses under reasonable assumptions;
- the certifier depends on the generator's claim-critical path;
- SWMM warnings, convergence, extraction, or version behavior falls outside the
  frozen protocol;
- a candidate requires more than one asset, more than two components,
  simultaneous pumping, or broader process/network simulation;
- latent or holdout-sensitive information would become agent-visible;
- a research path or raw engine artifact would become runtime authority;
- the promoted package cannot be self-contained; or
- the construct survives only by weakening a verifier or claim boundary.

The repair order is:

1. correct the derivation or implementation;
2. narrow the parameter envelope;
3. reject the fragile member;
4. replace the mechanism through a B2 amendment;
5. revisit the SWMM role through a B3 amendment; or
6. abandon the profile if the intended construct cannot survive.

Missing field data or SME review is not itself a stop while the family remains
explicitly synthetic and V4 is unclaimed.

## 14. Lineage and receipt protocol

Every B5 generation receipt must eventually bind:

- profile, B2 evidence pack, B3 engine decision, and B4 protocol identities;
- canonical parameter-family member and case identities;
- source/evidence and rights mapping;
- assumptions, units, transformations, and derivations;
- generator source identity and configuration;
- engine repository, version, commit, patch, executable, library, dependency,
  and configuration hashes;
- canonical input and semantic output hashes;
- warnings, errors, convergence, period count, and units;
- certifier source identity and dependency inventory;
- certification case identities and results;
- sensitivity design and result hashes;
- rejected-member reasons;
- visibility classifications;
- prohibited claims; and
- acceptance status and V-level evidence.

Canonical identity must be based on normalized content, not absolute paths,
temporary directory names, timestamps, mutable aliases, or log locations.

## 15. Promotion-manifest specification

B4-W5 must define a research-side canonical manifest specification. It remains
conceptual during B4 and becomes an exact B5 artifact; it is not a Pydantic
model or global repository contract.

The specification must include:

- manifest and profile version;
- exact accepted generation identity;
- earned V-level and supporting certification identity;
- exact promoted file allowlist with hashes, sizes, media types, and semantic
  roles;
- exact promoted field allowlist where a file contains mixed material;
- units, derivation, assumption, source, and rights references;
- public/agent-visible, host-private, certification-private, and
  holdout-sensitive classifications;
- generator and engine lineage required for audit but not runtime execution;
- independent-certification result references;
- schema/reader compatibility expectation for ASW-2A0;
- prohibited claims and envelope limits;
- unknown-file and unknown-field rejection requirements; and
- supersession and retirement metadata.

The manifest must exclude:

- source documents and copied cite-only content;
- research reports and notes;
- generator and certifier source;
- SWMM source, binaries, raw inputs, outputs, and reports;
- build/install trees and local receipts;
- rejected candidates;
- sealed certification cases and gold trajectories;
- mutable paths and aliases; and
- any field reserved without a named producer, consumer, authority, and
  visibility rule.

## 16. Contract and boundary register for B4

| Candidate exchange | Producer and consumer | Authority | Persistence/visibility | B4 maturity and rule |
| --- | --- | --- | --- | --- |
| Parameter-family declaration | B5 research generator and B5 research certifier | B4 physical protocol | Research-private, content-addressed | Conceptual specification only; no production model |
| Generator request/result | B5 generator and B5 certifier/promotion review | B4 generator protocol | Research-private; semantic result may be promotion input | Conceptual; no import from `src/aec_bench` |
| Certification request/result | B5 certification runner and B5 promotion review | B4 certification protocol | Certification-private plus compact public decision | Conceptual; separately executable path required |
| Promotion manifest | B5 promotion authority and later ASW-2A0 reader | B5 accepted generation under B4 specification | Rights-cleared, content-addressed; visibility explicit | Conceptual in B4, exact research artifact in B5, strict asset-local reader in ASW-2A0 |
| Promoted asset package | B5 promotion and later ASW-2A0 reader | Asset-local package under exact manifest | Runtime input; research absent | Not created in B4 |

No B4 exchange is added to `src/aec_bench/contracts`, re-exported, registered,
persisted in `TrialRecord`, exposed through CLI/Harbor, or described as a
repository contract.

## 17. AG-01 through AG-13 coverage plan

| Gate | B4 protocol responsibility | B5 evidence required |
| --- | --- | --- |
| `AG-01` | Freeze evidence-supported mechanism forms, synthetic family, envelope, sensitivities | Accepted members remain robust under preregistered tests |
| `AG-02` | Enforce one asset and exactly two pump components | Generated package contains no broader managed asset |
| `AG-03` | Select primary and secondary mechanisms | Both mechanisms execute and certify |
| `AG-04` | Define no-maintenance adverse consequence and ordering | Certified no-maintenance cases demonstrate it |
| `AG-05` | Freeze distinct calendar/runtime/start clocks | Replay proves divergent accumulation |
| `AG-06` | Freeze latent/observable mapping | Certified ambiguous-observation cases |
| `AG-07` | Define physical effects for deferral, restriction, inspection, intervention, verification | B5 physical cases support later action semantics |
| `AG-08` | Freeze one bounded access/outage/spare/lead-time constraint | Constraint changes at least one certified consequence |
| `AG-09` | Freeze retained state/history after intervention | Repair/clearance cases prove non-erasure |
| `AG-10` | Freeze separately executable certifier and independence rules | Independent certification passes without generator decision code |
| `AG-11` | Freeze paired-history construction | Same-reading/different-history pair certifies |
| `AG-12` | Freeze lineage, rights, units, assumptions, exclusions, manifest | Complete content-addressed receipts and rights review |
| `AG-13` | Bound family, horizon, cases, and deterministic execution | Complete local replay remains small and deterministic |

B4 defines the evidence contract for each gate. It does not mark a gate passed.

## 18. Review and verification strategy

### 18.1 Planning slice

Because B4-W0 changes only Markdown and `.gitignore`, its focused checks are:

- exact predecessor hashes;
- Markdown structure and internal consistency review;
- all required B4 decisions and AG gates mapped;
- `git diff --check`;
- changed-path review against the two-file allowlist; and
- confirmation that no ignored research output or production file appears.

No repository test suite is justified for this documentation-only slice.

### 18.2 Later protocol slices

Documentation-only B4 slices use focused structural and traceability checks.
If any executable validator or canonicalizer is introduced, that slice must use
TDD and include focused unit, integration, and end-to-end coverage of its real
research boundary. No mock SWMM or fallback engine is permitted.

B5 implementation must demonstrate:

- real pinned-engine generation;
- separately executed certification;
- deterministic regeneration;
- invalid-case rejection;
- sensitivity execution;
- receipt reload;
- manifest self-containment; and
- physical absence of unpromoted research material during package validation.

## 19. B3 retirement protocol

The B3 spike remains tracked while it is the executable evidence behind the
engine-role decision.

Its executable subtree may be removed from the current repository tree only
after:

1. B5 promotes at least one V3 generation under an exact manifest;
2. ASW-2A0 implements the strict asset-local reader;
3. the promoted package loads and its certification references replay with
   research and source directories physically absent;
4. the promotion and reader records cite the B3 commit needed for historical
   reproducibility; and
5. a dedicated retirement PR removes the B3 source, tests, fixture, patch, and
   `.gitignore` exceptions while retaining the compact role decision and
   verification summary.

Deletion removes the spike from the current tree, not Git history. This is
intentional: current users see the promoted implementation, while the
historical engine decision remains auditable.

## 20. B4 completion gate

B4 is accepted only when:

- every `B4-D01` through `B4-D17` row has an explicit ruling;
- the original synthetic family is fully dimensioned, bounded, and traced;
- primary and secondary mechanisms are accepted with falsification rules;
- transfer physics, observation mapping, intervention effects, clocks, and
  the resource constraint are frozen without scenario/authority leakage;
- generator inputs/outputs and fail-closed behavior are complete;
- independent-certifier methods and prohibited dependencies are complete;
- tolerances and sensitivity cases are preregistered;
- rejection, repair, stop, and pivot rules are executable without judgment
  invented after results;
- lineage receipts and the promotion-manifest specification are complete;
- AG-01 through AG-13 map to concrete B5 evidence;
- no production contract, runtime dependency, or generated family exists;
- repository boundary and visibility review passes; and
- an explicit acceptance record opens B5 as the only next stage.

If these conditions are not met, B4 remains open or returns to B2/B3. Partial
documentation does not authorize B5.

## 21. Immediate next task

After this plan is reviewed and merged, begin **B4-W1 — Parameter family and
mechanism rulings** in a fresh worktree.

The first B4-W1 decision should be the minimum original hydraulic base and
parameter-group derivation. Mechanism equations must not be selected until that
base establishes:

1. the valid clean pump/system operating envelope;
2. wet-well volume balance;
3. the distinct calendar/runtime/start clocks;
4. the information required to test obstruction applicability; and
5. whether the declared synthetic pump configuration can legitimately support
   hydraulic-clearance loss.

This ordering prevents an attractive degradation equation from silently
dictating the asset it was supposed to describe.
