# ABOUTME: Freezes the B4-W2 offline SWMM generator protocol for the first synthetic pump-set family.
# ABOUTME: Defines research-only input, mapping, extraction, replay, and failure rules without implementing a generator or runtime contract.

# AU-NSW-LH-SYN-SPS-v1 — Offline generator protocol

## 1. Decision identity

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B4 — Generator and certification protocol` |
| Internal work package | `B4-W2 — Generator protocol` |
| Status | **Accepted for B4 protocol design only; amended by the pre-W4 horizon repair** |
| Repository baseline | `54c31cb4a3550fd1ae33efa2eb5ce7e4253b6468` |
| Horizon-repair baseline | `eed52934b3fba5b17b9901df0d23a8120febcc0f` |
| Parent PRD SHA-256 | `56d6fe6a9c69796d819a1995ae63a85392ba85a4240df8baa87df99a76678335` |
| B1 claim/profile SHA-256 | `1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954` |
| B2 evidence/rights SHA-256 | `8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96` |
| B3 engine-role decision SHA-256 | `90603ddd481c0b627ad5e8ae5e0fc45f4c73b3910c86a8038cd80ce8eb80303d` |
| B3 compact verification SHA-256 | `db93443b31a197864709e7011af8a6aa15932cbec3260cf1a2afed735ffa3f11` |
| B4 execution-plan SHA-256 | `fad8cb04fad9729a81466e4527e38bcf42cffcc11c940423f610b6ffb8d8118e` |
| B4-W1 family authority SHA-256 | `337aeab9465a8a1801b67c2ab0b408a2a2f07becddffc4a02161b64e6a8630de` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Generator protocol identity | `asw-0b4.generator-protocol.v2` |
| Next permitted internal package | `B4-W3 — Independent certification protocol` only |

This record resolves only `B4-D12`. Decisions `B4-D13` through `B4-D17`
remain open under W3 through W5. This record does not implement the generator,
run SWMM, certify or promote a family member, create a world, open B5, or earn
a V-level.

### 1.1 Pre-W4 forced-horizon repair

W4 preflight review found that the original `1,200 s` forced-on snapshots
could leave the positive-storage operating envelope before their terminal
period. The W1 anchor clean assessment reaches zero depth at approximately
second `1,146`, and the original G70 clean Pump B segment reaches zero depth
at approximately local second `639`. W1 defines no dry-pump, starvation,
cavitation, or below-storage-boundary physics. W4 therefore cannot hide that
undefined regime inside a numerical tolerance.

This amendment:

- advances the generator protocol identity from `v1` to `v2`;
- derives a bounded forced-snapshot duration from the complete W1 envelope;
- changes individual forced hydraulic snapshots to `120 s`;
- changes each G70 segment to `60 s`, for a `120 s` complete sequence;
- makes each G80 checkpoint an explicit `120 s` forced snapshot; and
- leaves every W1 parameter, equation, case purpose, engine setting, semantic
  output, serialization rule, and claim boundary unchanged.

No generator or candidate output was run to select these durations. Generator
protocol `v1` remains historical review evidence but is not an allowed B5
request identity.

## 2. Authority, maturity, and placement

The parent PRD and accepted B1–B3, W0, and W1 records remain higher authority.
W1 owns the physical family. W2 owns the research generator protocol that
materializes bounded hydraulic cases from that family.

This file is a complete implementation specification for a later B5 research
generator. It is not:

- an importable repository contract;
- a production serializer or schema;
- a runtime asset package;
- a certification result;
- a promoted parameter member;
- an agent-visible engineering tool;
- a live solver integration;
- an action, authority, obligation, or study protocol; or
- permission to reuse B3 source names, fixtures, layouts, values, or
  tolerances.

The later implementation must be built as new B5 research code. It may consult
this authority and official pinned engine interfaces, but it must not import
the B3 Python package or treat this Markdown structure as executable input.
Production code must run with `research/` physically absent.

## 3. Work-package boundary

### 3.1 Allowed files

- `.gitignore`
- this generator-protocol record

### 3.2 Forbidden changes

B4-W2 does not change:

- `src/aec_bench`;
- the B3 spike or any predecessor authority;
- production contracts, exports, registries, CLI, Harbor, `TrialRecord`,
  harness, evaluation, providers, or runtime surfaces;
- the W1 physical family, values, equations, bounds, or claims;
- independent-certifier equations or numerical methods;
- numerical acceptance tolerances;
- sensitivity-grid values;
- lineage-receipt or promotion-manifest schemas;
- B3 retirement evidence;
- scenario timing, institutional actions, authority, obligations, handover,
  treatments, endpoints, scoring, or budgets; or
- any generated SWMM input, output, report, binary, log, receipt, or semantic
  case.

## 4. `B4-D12` ruling

| Decision | Ruling | Meaning |
| --- | --- | --- |
| `B4-D12` generator decomposition | **Accept, asymmetric and fail-closed** | A new B5 research generator validates canonical W2 requests, materializes W1 curves and cases, runs pinned SWMM offline, extracts an allowlisted semantic result, and proves deterministic replay. SWMM owns candidate hydraulic consequences only. |

The accepted decomposition is:

```text
canonical W2 request
        |
        v
independent pre-engine validation of W1 membership
        |
        v
deterministic curve and engine-model materialization
        |
        v
pinned SWMM 5.2.4 offline execution
        |
        +--> solver step API: exact pump link settings at report instants
        |
        +--> official output API: allowlisted hydraulic series
        |
        +--> report parser: warnings, errors, convergence, continuity metadata
        |
        v
path-free canonical semantic candidate + hashes
        |
        v
second fresh execution with identical semantic hash
```

The generator may state only that a candidate executed and satisfied W2
structural gates. It cannot certify physical coherence, choose a tolerance,
approve sensitivity robustness, promote an artifact, award benchmark success,
or become runtime truth.

## 5. Engine-interface evidence and rights

| ID | Interface evidence | Accepted use | Rights and limit |
| --- | --- | --- | --- |
| `W2-E01` | Accepted B3 engine-role decision and compact verification | Exact source/version role, public-domain source notice, build boundary, output-API capability, replay evidence, and non-promotion boundary | Repository-authored evidence; B3 diagnostic values, code layout, and tolerances remain non-authoritative |
| `W2-E02` | EPA, [*Storm Water Management Model User's Manual Version 5.2*](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P10145M6.TXT) | Input-section semantics for direct inflows, PUMP3 curves, storage, fixed-stage outfalls, force mains, and time-series interpolation | `Cite-only`; documentation of engine interface, not profile-value or physical-claim authority |
| `W2-E03` | Pinned official [`swmm_output_enums.h`](https://raw.githubusercontent.com/USEPA/Stormwater-Management-Model/7952ca837988b1c32f791812eccc9fd64547e093/src/outfile/include/swmm_output_enums.h) and [`swmm_output.h`](https://raw.githubusercontent.com/USEPA/Stormwater-Management-Model/7952ca837988b1c32f791812eccc9fd64547e093/src/outfile/include/swmm_output.h) | Exact official output attributes and API boundary at the accepted commit | Official pinned public-domain source; interface facts only |
| `W2-E04` | Pinned official [`src/solver/include/swmm5.h`](https://github.com/USEPA/Stormwater-Management-Model/blob/7952ca837988b1c32f791812eccc9fd64547e093/src/solver/include/swmm5.h) in the B3-recorded solver library | `swmm_open/start/step/end/report/close`, `swmm_getValue`, and `swmm_LINK_SETTING` for offline stepping and exact link-setting capture | Research generator only; no runtime, agent-tool, or certifier use |

The official output API exposes node depth, head, stored volume, lateral
inflow, flooding, link flow, and link capacity. It does not expose a pump
status series. W2 therefore prohibits reconstructing status from flow alone:
the offline generator must record exact `swmm_LINK_SETTING` values while
stepping the pinned solver and must cross-align those settings with output
periods.

No engine-interface source supplies a W1 profile value. All W1 values retain
their W1 evidence and rights disposition.

### 5.1 W2 engine-mapping assumption register

| ID | W2 construction | Class and rights | Claim ceiling and later check |
| --- | --- | --- | --- |
| `W2-A01` | Fixed engine date origin `01/01/2002 00:00:00` | Original `S`; redistributable under repository licence | Engine time-index origin only; never world calendar time |
| `W2-A02` | Fixed-HGL outfall and initially full horizontal force-main mapping | Derived from W1 `system.z_d`, `system.D`, and official engine interface semantics | No real outfall, valve, pipe profile, or station-arrangement claim; W3 checks head identities and W4 checks sensitivity |
| `W2-A03` | Engine-only conduit Manning sentinel `0.0125` | Original `S`; redistributable under repository licence | Not a W1 roughness or pipe-material value; full-pipe diagnostic and W4 perturbation prevent it from becoming claim-critical |
| `W2-A04` | Thirty-two-segment PUMP3 reference discretization | Original `S`; redistributable under repository licence | Numerical representation only; W4 curve-resolution sensitivity required |
| `W2-A05` | One-second fixed routing, rule, and report grid | Original derived setting; redistributable under repository licence | W2 deterministic reference only; W4 resolution sensitivity required |
| `W2-A06` | Zero-inflow static-storage limiting case | Original `S`; redistributable under repository licence | Explicitly outside the W1 member family and never promotable |

## 6. Role and ownership matrix

| Concern | W2 producer | Permitted consumer | Authority | Explicit non-owner |
| --- | --- | --- | --- | --- |
| Canonical research request | B5 case planner | B5 generator validator | W1 physical family plus W2 protocol | Production runtime |
| Materialized pump curves | B5 generator preprocessor | SWMM renderer and later W3 certifier as input evidence | W1 equation, W2 sampling rule | SWMM |
| Rendered `.inp` | B5 renderer | Pinned SWMM only | W2 engine mapping | Runtime or promotion |
| Binary `.out` | Pinned SWMM | Official output extractor only | Engine evidence | Runtime, actor, certifier, promotion |
| Human-readable `.rpt` | Pinned SWMM | W2 diagnostic parser only | Engine diagnostic evidence | Replay or semantic truth |
| Pump setting trace | B5 offline solver-step recorder | W2 semantic assembler and W3 certifier | Exact engine setting at report instant | Flow inference |
| Hydraulic semantic candidate | W2 semantic assembler | W3 certifier and later W5 promotion review | Candidate evidence only | Runtime before promotion |
| Generator finding | B5 generator | B5 orchestration and reviewer | W2 structural protocol | Physical certification |

No row creates a contract under `src/aec_bench/contracts`, a persisted
`TrialRecord` field, a CLI surface, or a production import.

## 7. Canonical research request

### 7.1 Conceptual top-level classes

The canonical request contains exactly five conceptual objects:

| Object | Required contents |
| --- | --- |
| `authority` | Protocol identity, profile identity, exact W1 hash, research-only scope, non-promotable request flag |
| `member` | Exact W1 stable parameter identities, canonical SI decimal values, units, and member-content identity |
| `case` | W2 case ID, family, pump-label assignment, control mode, latent state, exposure state, initial depth, inflow stimulus, duration, and any W2-authorized physical transition |
| `engine` | Official repository, version, commit, portability-patch hash, build-receipt hash, executable hash, solver-library hash, output-library hash, and frozen settings identity |
| `outputs` | Exact ordered semantic output request allowlist |

Filesystem paths, hostnames, usernames, timestamps of execution, temporary
directory names, environment-variable names, log paths, and report paths are
not canonical request content.

### 7.2 Canonical scalar representation

- Canonical physical scalars are UTF-8 decimal strings in SI.
- The grammar is `-?(0|[1-9][0-9]*)(\.[0-9]+)?`.
- Exponents, leading plus signs, leading zeroes, decimal commas, `NaN`,
  infinity, negative zero, and unit-bearing strings are rejected.
- Each scalar has a separate exact unit token from the W1 unit register.
- Counts and ordinal indices are JSON integers, not decimal strings.
- Booleans are JSON booleans.
- Enumerated values are exact lower-case ASCII tokens.
- Null, duplicate keys, comments, unknown keys, and Unicode lookalikes are
  rejected.
- Canonical JSON uses UTF-8, LF, no BOM, lexicographically ordered object keys,
  fixed array order, no insignificant whitespace, and one terminal LF.
- Canonical derivation arithmetic uses decimal precision 34 with
  round-half-even. Engine-rendered lengths and heads are quantized to
  `0.000000001 m`; engine-rendered flows are quantized to
  `0.000001 L/s`.

The decimal policy is a research serialization decision, not a production
schema. W3 must independently parse the same canonical bytes without importing
the generator.

### 7.3 Stable content identities

```text
member_content_id =
    sha256("asw-0b4.member.v1\0" || canonical_member_bytes)

case_content_id =
    sha256("asw-0b4.case.v1\0" || canonical_case_bytes)

request_content_id =
    sha256("asw-0b4.generator-request.v1\0" || canonical_request_bytes)
```

The literal domain prefixes and NUL separators are part of W2. Hashes are
lower-case hexadecimal SHA-256. A caller-supplied identifier that differs from
the recomputed identity rejects the request.

`request_content_id` is the W2 generation identity. A replay ordinal, process
ID, local path, or execution timestamp never changes it.

### 7.4 Parameter member completeness

The `member` object must contain every W1 stable parameter identity exactly
once. Fixed composite values, including the inflow pattern, severity domain,
inspection bands, topology limits, and resource booleans, are present by
identity even when a W2 hydraulic case does not exercise them.

The generator:

- accepts no defaulted parameter;
- performs no unit inference;
- performs no bound clamping;
- performs no alias translation;
- recomputes all W1 derived values;
- rejects a mismatch between declared and derived values; and
- never reads parameter values from this Markdown file at execution time.

B5 must implement a new machine-readable research declaration whose bytes are
content-addressed and reviewed against W1. That declaration is research input,
not a promoted runtime package.

### 7.5 Physical transition representation

The canonical case contains an ordered `physical_transitions` array. It is:

- empty for an unmodified snapshot;
- one exact time-zero W1 intervention effect for G51, G53, and G61;
- one A-to-B transfer at the G70 segment boundary; and
- otherwise forbidden by the W2 catalogue.

Each entry states the local effective second, effect kind, target pump,
before-state content identity, after-state content identity, and the W1 rule
identity that derives the change. It contains no actor, authorization, work
order, obligation, reason, closure, or score.

Time-zero intervention effects are applied before curve materialization. They
do not mutate a curve during a SWMM segment. G70 materializes a separately
identified curve and engine input for each segment.

## 8. Validation order and deterministic failures

Validation occurs in this exact order. The first failure terminates the request
before any later phase executes.

| Order | Failure family | Check |
| ---: | --- | --- |
| 1 | `request-bytes` | UTF-8, BOM, newline, duplicate-key, JSON, scalar grammar, and canonical-byte checks |
| 2 | `request-shape` | Exact top-level objects, exact nested keys, exact ordered arrays, no unknown field |
| 3 | `authority` | Protocol/profile identities, W1 hash, research-only scope, non-promotion assertion |
| 4 | `content-identity` | Member, case, and request hashes recompute exactly |
| 5 | `units` | Exact W1 identity-to-unit mapping and dimensional category |
| 6 | `member-bounds` | Every value finite, present, inside inclusive W1 bounds, and fixed values exact |
| 7 | `member-cross-constraint` | All W1 section 16 ordering, geometry, operating-point, topology, history, and intervention constraints |
| 8 | `case-authorization` | Case ID, family, control mode, state, stimulus, duration, transitions, and requested outputs are W2-allowlisted |
| 9 | `curve-materialization` | Positive support, exact point count, strict head ordering, non-increasing flow, no duplicate after quantization |
| 10 | `engine-settings` | Exact W2 settings and section allowlist; no implicit override |
| 11 | `engine-build` | Repository, version, commit, patch, receipt, executable, solver library, output library, and relevant upstream test |
| 12 | `workspace` | New absent run root; distinct non-existing input, report, output, trace, and semantic paths |
| 13 | `render` | Exact element set, section set, unit conversions, input bytes, and rendered-input hash |
| 14 | `execute` | Offline solver lifecycle, return codes, completion, files, and exact pump-setting trace alignment |
| 15 | `extract` | Output version, unit code, periods, report step, element identities, attribute lengths, finite values, and SI conversion |
| 16 | `diagnostics` | No engine error, warning, missing marker, or non-converging step; continuity value present and finite |
| 17 | `semantic-shape` | Exact series IDs, lengths, units, representations, time grid, setting domain, and no path-dependent content |
| 18 | `replay` | Second fresh workspace, same canonical request, rendered input, setting trace, and semantic hash |

Failures are data, not permission to weaken a check. W4 later defines
numerical, residual, and sensitivity rejection thresholds; W2 never invents
one from observed output.

## 9. Exact SWMM role and model mapping

### 9.1 Engine pin

| Item | Required identity |
| --- | --- |
| Official repository | `https://github.com/USEPA/Stormwater-Management-Model.git` |
| Version | `5.2.4` |
| Commit | `7952ca837988b1c32f791812eccc9fd64547e093` |
| Output version integer | `52004` |
| Flow unit | `LPS`, official output code `4` |
| Portability patch SHA-256 | `522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894` |
| Build type | `Release` |
| Engine parallelism | one thread |

A B5 build may have new executable and library hashes only when its own fresh
build receipt proves the exact repository, commit, patch, build type, toolchain,
dependency inventory, and relevant upstream output-API test. The generator
binds that receipt and rechecks those actual artifact hashes before every run.
Cross-workspace byte-identical builds are not assumed.

### 9.2 Stable research engine identifiers

| W1 concept | W2 engine identifier | SWMM element |
| --- | --- | --- |
| Wet well | `WW_B4` | cylindrical storage node |
| Pump A | `L_PA` | PUMP3 link |
| Pump B | `L_PB` | PUMP3 link |
| Discharge header | `J_DIS` | junction node |
| Fixed discharge HGL | `O_HGL` | fixed-stage outfall |
| Force main | `L_FM` | FORCE_MAIN conduit |
| Pump A curve | `C_PA` | PUMP3 curve |
| Pump B curve | `C_PB` | PUMP3 curve |
| External inflow | `TS_IN` | direct-inflow time series |

These identifiers are research rendering constants, not production component
IDs. The semantic layer maps `L_PA` and `L_PB` back to the W1 labels Pump A and
Pump B.

### 9.3 Allowed input sections

The renderer emits only:

```text
[TITLE]
[OPTIONS]
[JUNCTIONS]
[OUTFALLS]
[STORAGE]
[INFLOWS]
[PUMPS]
[CONDUITS]
[XSECTIONS]
[CURVES]
[TIMESERIES]
[REPORT]
```

The order is exact. Empty, duplicate, unknown, hydrology, rainfall, catchment,
pollutant, treatment, groundwater, RDII, actuator-control, map, coordinate,
label, tag, or free-form metadata sections reject before execution.

### 9.4 Wet well and overflow

`WW_B4` is mapped as:

| SWMM property | W1 source |
| --- | --- |
| Invert elevation | exact `0 m` datum |
| Maximum depth | `well.h_overflow` |
| Initial depth | exact W2 case value within `[well.h_stop, well.h_overflow]`, except the explicit zero-inflow boundary |
| Shape | `CYLINDRICAL` |
| Major and minor axis | `well.D_w` |
| Side slope | exact `0` |
| Surcharge depth | exact `0` |
| Ponded area | exact `0` |
| Evaporation factor | exact `0` |

`ALLOW_PONDING` is `NO`. Flow exported as node flooding at `WW_B4` is the
candidate overflow rate. W2 does not convert that rate to an accepted overflow
volume; W3/W4 own integration and tolerance.

### 9.5 Fixed discharge boundary and full force main

W1 defines `system.z_d` as the discharge hydraulic-grade elevation. To avoid
turning the ordinary conduit Manning field into hidden physical authority, W2
keeps the force main full against a fixed-stage boundary:

```text
force_main_invert = system.z_d - system.D
outfall_fixed_stage = system.z_d
```

`J_DIS` and `O_HGL` use `force_main_invert`. `J_DIS` starts at depth
`system.D`, has maximum depth `system.D`, surcharge depth equal to the W1 upper
bound of `pump.H_0`, and zero ponded area. `O_HGL` has type `FIXED`, stage
`system.z_d`, and no flap gate. Thus the pipe crown and initial water surface
coincide with the fixed HGL before pumping.

`L_FM` maps:

| SWMM property | W2 value |
| --- | --- |
| From/to | `J_DIS` to `O_HGL` |
| Length | `system.L` |
| Inlet/outlet offsets | exact `0` |
| Initial flow | exact `0 L/s` |
| Maximum flow override | absent/default unlimited |
| Cross-section | `FORCE_MAIN` |
| Diameter | `system.D` |
| Darcy-Weisbach roughness height | `system.epsilon × 1000`, in millimetres |
| Barrels | exact `1` |
| Conduit Manning sentinel | exact `0.0125`, dimensionless, engine-only |

The sentinel is not a pipe-material claim or W1 physical parameter. The
official engine uses the force-main cross-section roughness height for
pressurized Darcy-Weisbach loss; ordinary Manning roughness could matter if
the link ceases to be full. The generator therefore extracts
`force_main_capacity_fraction` for every report period. W3/W4 must reject any
claim-critical case in which full-pipe behavior is not independently
established. W4 must perturb the sentinel as an engine-boundary sensitivity.
W2 does not choose that perturbation or its tolerance.

### 9.6 Pump links and controls

Each pump is a link from `WW_B4` to `J_DIS` with its own materialized PUMP3
curve.

For an automatic-duty case:

- the assigned duty pump starts at `well.h_start`;
- it shuts off at `well.h_stop`;
- it is initially `OFF`;
- the non-duty pump is `OFF` with no automatic activation; and
- a setting outside exact `{0, 1}` rejects.

For a forced hydraulic snapshot:

- the selected pump is `ON` for the complete segment;
- the other pump is `OFF`;
- start/stop thresholds are disabled for that segment; and
- the case is diagnostic hydraulic evidence, not an operating instruction.

For a transfer sequence, W2 uses two separate fresh engine segments. Segment
A has Pump A forced on and Pump B off. Segment B carries the exact final wet
well depth into a new input, has Pump A off and Pump B forced on, and retains
both pumps' latent and exposure state in canonical case metadata. The fixed
full-line boundary prevents a hidden force-main fill state from becoming a
cross-segment carrier.

No case uses simultaneous pumping, periodic alternation, assist operation,
variable speed, fractional setting, or more than one A-to-B transfer.

### 9.7 Direct inflow

Direct FLOW inflow enters `WW_B4` through `TS_IN` with:

- scale factor exact `1`;
- baseline exact `0 L/s`;
- no periodic pattern; and
- elapsed time measured from the fixed engine origin.

The W1 base pattern is rendered at one-second boundaries:

| Elapsed second | Value |
| ---: | --- |
| `0` | `Q_in_low` |
| `5,399` | `Q_in_low` |
| `5,400` | `Q_in_nominal` |
| `10,799` | `Q_in_nominal` |
| `10,800` | `Q_in_assess` |
| `14,399` | `Q_in_assess` |
| `14,400` | `Q_in_nominal` |
| `21,599` | `Q_in_nominal` |
| `21,600` | `Q_in_low` |
| `28,800` | `Q_in_low` |

SWMM interpolates non-rainfall time series. The paired boundary points make
each change occur across exactly one fixed routing interval rather than across
the preceding block. The generator exports the actual engine lateral-inflow
series, so W3 certifies the volume that SWMM received rather than trusting the
intended table.

Constant diagnostic cases use two equal-valued points at second `0` and the
case horizon. The explicit zero-inflow boundary uses exact zero and is marked
`non_promotable_boundary=true`; it is not a W1 family member.

### 9.8 Rendered input byte profile

Rendered SWMM input bytes are deterministic:

- encoding is seven-bit ASCII, a strict subset of UTF-8;
- line ending is LF;
- no BOM, tab, trailing space, blank leading line, or extra terminal blank line
  is permitted;
- the file ends with exactly one LF;
- section and element order follow sections 9.2 and 9.3;
- keywords and W2 engine identifiers use exact upper-case spelling;
- fields are separated by one ASCII space rather than alignment padding;
- comments are absent;
- `[TITLE]` contains one line formed from profile ID, case ID, and
  `request_content_id`, separated by one space;
- lengths, levels, heads, and dimensionless engine decimals have exactly nine
  digits after the decimal point;
- flows have exactly six digits after the decimal point in `LPS`;
- integer counts have no decimal point;
- elapsed times use zero-padded `HH:MM:SS`;
- scientific notation is forbidden; and
- curve and time-series rows follow their frozen numerical order.

The renderer first constructs this complete byte sequence in memory, validates
its section and identifier allowlists, calculates its SHA-256, and only then
writes once to an absent input path. The hash never depends on a path or
platform newline convention.

## 10. Pump-curve materialization

### 10.1 Exact transformation

For each pump state `(o, c)`:

```text
A = 1 - a_o o - a_c c
B = 1 + b_o o + b_c c
Q_support = Q_0 sqrt(A / B)
```

The W1 bounds guarantee positive `A` and `B`; W2 nevertheless rejects a
non-positive value.

The original curve is represented with exactly `N = 32` equal flow segments
and `33` PUMP3 points. For `j = 0 ... 32`:

```text
Q_j = Q_support (1 - j / 32)
H_j = H_0 [A - B (Q_j / Q_0)^2]
```

Points are rendered in `j` order:

- head `H_j` is the PUMP3 X value in metres and must increase strictly after
  quantization;
- flow `1000 Q_j` is the PUMP3 Y value in litres per second and must not
  increase;
- point `j = 0` is zero head at maximum support flow; and
- point `j = 32` is the degraded shutoff head at zero flow.

The generator uses the decimal policy in section 7.2, rejects duplicate or
non-monotone points after quantization, and records the canonical curve-point
hash separately for Pump A and Pump B.

Before quantization, the compiler sets the `j = 0` head to exact zero and the
`j = 32` flow to exact zero. This prevents an irrational square-root rounding
residue from turning either physical endpoint into a hidden non-zero value.

The W2 reference resolution is not a physical truth or acceptance tolerance.
W4 must preregister curve-resolution perturbation. A case whose qualitative
outcome depends on the chosen piecewise resolution is rejected or narrowed.

### 10.2 Label symmetry and state ownership

At matched `(o, c)`, Pump A and Pump B curves must have identical point bytes.
At different states, each pump retains its own curve and content identity.
Transfer swaps physical duty assignment; it does not swap, reset, or relabel
the curve states.

The curve compiler implements only the W1 transformation. It does not solve
the system operating point, certify monotonicity, or reuse a certifier helper.

## 11. Frozen engine settings

### 11.1 Settings table

| Setting | W2 value |
| --- | --- |
| Engine date origin | `01/01/2002 00:00:00` |
| Flow units | `LPS` |
| Flow routing | `DYNWAVE` |
| Force-main equation | `D-W` |
| Link offsets | `DEPTH` |
| Routing step | `1 s`, fixed |
| Rule step | `1 s`, fixed |
| Report step | `1 s`, fixed |
| Wet step | `1 s`, fixed |
| Dry step | `1 s`, fixed |
| Variable step | disabled, exact `0.00` |
| Threads | exact `1` |
| Ignore rainfall | `YES` |
| Allow ponding | `NO` |
| Skip steady state | `NO` |
| Report start | engine start |
| Report averages | `NO` |
| Report elements | exact W2 node/link allowlist |

Other SWMM options are omitted and therefore take the pinned 5.2.4 defaults.
Those defaults are part of the engine-source identity. An implementation that
explicitly overrides an omitted option is a different settings identity and
rejects under W2.

### 11.2 Routing-step derivation

At the most conservative W1 bounds:

```text
minimum wet-well area
    = pi (2.80 m)^2 / 4
    = 6.157521601... m²

upper absolute flow bound
    = Q_0,max + Q_in_assess,max
    = 0.046 + 0.016
    = 0.062 m³/s

upper one-second level movement
    = 0.062 / 6.157521601...
    = 0.010068986... m

minimum control hysteresis
    = h_start,min - h_stop,max
    = 1.50 - 0.85
    = 0.65 m
```

One second is less than two percent of the minimum hysteresis even under the
conservative summed-flow bound. The report step equals the routing and rule
step so pump setting, level, flow, runtime, and starts can share one exact time
grid. This derivation is independent of B3's disposable one-second setting.

W4 must perturb routing/report resolution and decide whether the qualitative
case outcomes are stable. W2 claims only a deterministic reference setting.

### 11.3 Expected periods

For every segment:

```text
expected_periods = horizon_seconds / report_step_seconds
```

The horizon must be positive and exactly divisible by one second. Period zero
is represented by canonical initial state, not duplicated as an engine output
period. Semantic time is therefore:

```text
t_seconds[k] = k + 1
for k = 0 ... expected_periods - 1
```

The W1 base case has exactly `28,800` output periods. Any extra, missing,
terminal, or differently spaced period rejects.

## 12. Diagnostic case catalogue

### 12.1 Catalogue rules

The catalogue stimulates the generator and later certifier; it is not the
stewardship study history. Unless stated otherwise, cases use the W1 anchor
member, fixed engine settings, initial depth `well.h_start`, Pump A as the
selected pump, Pump B off, and exact SI values.

Case order is the lexical order of the fixed IDs below. G70 segments are
ordered A then B. G80 checkpoints are ordered by checkpoint index zero through
three. Any later W4 sensitivity members inside one case/checkpoint are ordered
by canonical case-content ID. A different execution order is a protocol
failure even if outputs later happen to match.

Forced-case duration is a diagnostic-observation horizon, not the W1
`capability.t_draw_limit`. Capability remains an independent calculation at
`h_start`; a snapshot is not extended to the capability limit.

The forced horizons are bounded before execution from the most conservative
W1 combination:

```text
A_w,min
    = pi (2.80 m)^2 / 4
    = 6.157521601... m²

Q_net,draw,max
    = Q_0,max - Q_in_assess,min
    = 0.046 - 0.014
    = 0.032 m³/s

t_to_h_stop,min
    = A_w,min (h_start,min - h_stop,max) / Q_net,draw,max
    = 125.074657521... s

h_after_120,min
    = h_start,min - Q_net,draw,max (120 s) / A_w,min
    = 0.876372467... m

minimum margin above h_stop,max
    = 0.876372467... - 0.85
    = 0.026372467... m
```

The bound deliberately assumes continuous maximum support flow rather than a
smaller solved operating flow. It is therefore conservative without using a
generator result. Every individual forced-on snapshot in G12 through G61 and
each G80 checkpoint lasts `120 s`. G70 divides the same total duration into
two `60 s` segments, so the complete transfer sequence retains the same
positive margin even if both pumps sustain the conservative maximum net draw.

A request for one of those cases with another duration rejects. G00 remains
the separately declared `3,600 s` pumps-off static-storage boundary. If B5 or
W4 later shows that a claim-critical hydraulic transient cannot be assessed
inside this bounded window, the case returns for protocol repair; it does not
extend into an undefined dry-well regime.

### 12.2 Exact cases

| Case ID | Purpose | Hydraulic stimulus and state |
| --- | --- | --- |
| `G00_ZERO_STATIC` | Static-storage limiting boundary | `3,600 s`; zero inflow; both pumps forced off; initial depth `h_start`; explicitly outside family and non-promotable |
| `G10_CLEAN_A_BASE` | Clean automatic-duty base pattern | `28,800 s`; initial depth `h_stop`; W1 base inflow pattern; automatic Pump A thresholds; `(o_A,c_A)=(0,0)` |
| `G11_CLEAN_B_BASE` | Label mirror | Exact G10 inputs with Pump B automatic and Pump A off |
| `G12_CLEAN_ASSESS` | Clean capability snapshot | `120 s`; constant `Q_in_assess`; clean Pump A forced on |
| `G20_OBSTRUCTION_HALF` | Primary mechanism interior | `120 s`; constant `Q_in_assess`; Pump A `(0.50,0)` forced on |
| `G21_OBSTRUCTION_TRIGGER` | W1 primary trigger witness | `120 s`; constant `Q_in_assess`; Pump A `(0.75,0)` forced on |
| `G22_OBSTRUCTION_UPPER` | Primary upper state | `120 s`; constant `Q_in_assess`; Pump A `(1,0)` forced on |
| `G30_CLEARANCE_HALF` | Secondary mechanism interior | `120 s`; constant `Q_in_assess`; Pump A `(0,0.50)` forced on |
| `G31_CLEARANCE_UPPER` | Secondary upper state | `120 s`; constant `Q_in_assess`; Pump A `(0,1)` forced on |
| `G40_COMBINED_HALF` | Combined interior | `120 s`; constant `Q_in_assess`; Pump A `(0.50,0.50)` forced on |
| `G41_COMBINED_UPPER` | Combined upper state | `120 s`; constant `Q_in_assess`; Pump A `(1,1)` forced on |
| `G50_CLEAR_A_PRE` | Ambiguous-history A before clearing | `120 s`; constant `Q_in_assess`; Pump A `(0.65,0.10)` forced on |
| `G51_CLEAR_A_POST` | Ambiguous-history A after anchor clearing | Same as G50 with `o_A=0.0975`, `c_A=0.10`; histories retained |
| `G52_CLEAR_B_PRE` | Ambiguous-history B before clearing | `120 s`; constant `Q_in_assess`; Pump A `(0.25,0.742300)` forced on |
| `G53_CLEAR_B_POST` | Ambiguous-history B after anchor clearing | Same as G52 with `o_A=0.0375`, `c_A=0.742300`; histories retained |
| `G60_REPAIR_PRE` | Clearance repair before state | `120 s`; constant `Q_in_assess`; Pump A `(0.50,0.50)` forced on |
| `G61_REPAIR_POST` | Anchor repair effect | Same as G60 with `o_A=0.50`, `c_A=0.05`; histories retained |
| `G70_TRANSFER` | One physical A-to-B transfer sequence | Segment A: `60 s`, Pump A `(0.75,0)` forced on; Segment B: carry final well depth, Pump A off, clean Pump B forced on for `60 s`; constant `Q_in_assess` |
| `G80_NO_MAINTENANCE` | Progression checkpoint family | Four independent `120 s` forced-on capability snapshots at exposure `(0 s,0 starts)`, `(3,600,000 s,500)`, `(7,200,000 s,1,000)`, and `(10,800,000 s,2,000)`; each begins at `h_start` with constant `Q_in_assess`; severities are recomputed from exact W1 anchor rates and clipping, never copied as rounded constants |

### 12.3 Sequence assembly

G70 produces two segment results and one sequence result:

- segment A semantic time is seconds `1 ... 60`;
- segment B receives segment A's exact final binary32 wet-well depth as its
  initial-depth source, records that carry hash, and has local seconds
  `1 ... 60`;
- the sequence time grid is seconds `1 ... 120`;
- sequence series concatenate A then B without duplicating the boundary;
- segment diagnostics and hashes remain separate;
- the sequence semantic hash binds both ordered segment hashes and the carry
  identity; and
- latent state, exposure, intervention history, and duty assignment are
  retained in canonical case metadata rather than inferred from SWMM files.

If the carried depth is outside the W1 storage envelope, is not finite, or
cannot be rendered without changing its exact binary32 meaning, G70 rejects.

### 12.4 Case exclusions

The catalogue contains no:

- calendar placement in the later study;
- work order, inspection authority, restriction, or closure;
- crew schedule or procurement workflow;
- stochastic event;
- real failure;
- more than one transfer;
- simultaneous pumping;
- live mechanism mutation inside a SWMM segment;
- mutable pump curve inside an engine run; or
- gold answer.

Mechanism progression and intervention effects are W1 state transitions.
SWMM receives only the resulting fixed curve for each segment. This preserves
the engine's hydraulic role and prevents it from owning stewardship semantics.

## 13. Semantic output allowlist

### 13.1 Candidate hydraulic series

All series have exactly `expected_periods` values and canonical SI units.

| Semantic ID | Source | Canonical unit | Visibility at W2 |
| --- | --- | --- | --- |
| `time_s` | Independently derived integer grid | `s` | Research-private candidate |
| `wet_well_depth_m` | `WW_B4`, `SMO_invert_depth` | `m` | Research-private candidate |
| `wet_well_volume_m3` | `WW_B4`, `SMO_stored_ponded_volume` | `m³` | Research-private candidate |
| `wet_well_inflow_m3_s` | `WW_B4`, `SMO_lateral_inflow`, exact LPS-to-SI conversion | `m³/s` | Research-private candidate |
| `wet_well_overflow_m3_s` | `WW_B4`, `SMO_flooding_losses`, exact LPS-to-SI conversion | `m³/s` | Research-private candidate |
| `pump_a_flow_m3_s` | `L_PA`, `SMO_flow_rate_link`, exact LPS-to-SI conversion | `m³/s` | Research-private candidate |
| `pump_b_flow_m3_s` | `L_PB`, `SMO_flow_rate_link`, exact LPS-to-SI conversion | `m³/s` | Research-private candidate |
| `force_main_flow_m3_s` | `L_FM`, `SMO_flow_rate_link`, exact LPS-to-SI conversion | `m³/s` | Research-private candidate |
| `pump_a_setting` | Pinned solver step API, exact report instant | dimensionless exact `0` or `1` | Certification-private candidate |
| `pump_b_setting` | Pinned solver step API, exact report instant | dimensionless exact `0` or `1` | Certification-private candidate |

The W1 later actor-visible status projection may use the certified exact
setting plus assignment and hydraulic checks. W2 does not expose a status to
an actor or infer a diagnosis from flow.

### 13.2 Certification-only hydraulic diagnostics

| Semantic ID | Source | Unit | Purpose |
| --- | --- | --- | --- |
| `wet_well_head_m` | `WW_B4`, `SMO_hydraulic_head` | `m` | Pump-head and datum cross-check |
| `discharge_head_m` | `J_DIS`, `SMO_hydraulic_head` | `m` | Pump/system-head cross-check |
| `force_main_capacity_fraction` | `L_FM`, `SMO_capacity` | dimensionless | Prove full-pipe envelope |

These diagnostics are not presumptive promotion candidates. W5 decides whether
any compact derived evidence, rather than the series themselves, is needed in
a promotion manifest.

### 13.3 Run-level diagnostics

The generator records:

- engine version and flow-unit code;
- report step and independently expected period count;
- exact node/link counts, names, and order;
- process and solver lifecycle return codes;
- exact engine warnings and errors as normalized identifiers, with no raw
  report prose;
- completion-marker presence;
- percentage of steps not converging;
- convergence-at-all-steps marker;
- signed flow-routing continuity error percentage;
- input, report, binary output, setting-trace, semantic, executable, and
  library hashes; and
- replay equality findings.

The continuity value is evidence, not a W2 pass threshold. W4 owns its
preregistered treatment.

### 13.4 Explicit output exclusions

W2 excludes:

- power, current, efficiency, energy, NPSH, vibration, temperature, seal, and
  motor variables;
- inferred obstruction or clearance diagnosis;
- pump remaining life, failure probability, or reliability;
- engine-generated dates as world calendar time;
- unrequested node, link, system, pollutant, or subcatchment series;
- wall-clock timestamps;
- local paths;
- raw report text;
- report tables;
- console text;
- binary output bytes from the semantic payload; and
- any institutional, obligation, action, score, handover, or actor-visibility
  field.

An unknown output request rejects before rendering.

## 14. Extraction and semantic representation

### 14.1 Output metadata checks

Before reading a series, the output extractor verifies:

1. output version exact `52004`;
2. flow-unit code exact `4`;
3. report step exact `1`;
4. period count independently expected;
5. exact node set `{J_DIS, O_HGL, WW_B4}`;
6. exact link set `{L_FM, L_PA, L_PB}`;
7. exact element order recorded and name-to-index mapping constructed by name;
8. requested official attribute exists;
9. returned length equals period count; and
10. every returned value is finite.

The extractor never trusts a fixed element index from the renderer.

### 14.2 Canonical floating-series bytes

The official output library returns IEEE-754 binary32 values. For semantic
hashing:

- each value is first checked finite;
- negative zero is normalized to positive zero;
- the exact binary32 value is represented as eight lower-case hexadecimal
  digits in big-endian bit order;
- the series records its semantic ID, SI unit, engine source attribute,
  representation `ieee754-binary32-be-hex`, and ordered value array; and
- LPS-to-`m³/s` conversion is applied through an explicitly identified exact
  scale transformation, correctly rounded to binary32 using round-to-nearest
  ties-to-even, before a new binary32 semantic value is encoded.

The human review projection may display decimal values, but decimal formatting
is not the semantic hash input. W3 decodes the bit representation
independently.

Pump settings and `time_s` are exact integer arrays and do not use binary32
encoding.

### 14.3 Pump-setting alignment

The offline execution uses the pinned solver lifecycle:

```text
open -> start(save output) -> repeated step and setting capture
     -> end -> report -> close
```

At each exact one-second report instant, the recorder captures Pump A and Pump
B link settings. It rejects:

- a missing or duplicate instant;
- a setting outside exact `0` or `1`;
- simultaneous setting `1`;
- a duty-label mismatch;
- a setting trace shorter or longer than the output series;
- a transfer outside the G70 segment boundary; or
- an API error hidden by successful binary output.

The binary output API remains the source of hydraulic series. The solver
setting trace is the source of control state. Neither is accepted as an
independent certifier.

## 15. Report, warning, and convergence policy

### 15.1 Fail-closed report handling

The report parser is version-bound and accepts only normalized diagnostic
facts. It rejects when:

- engine process or lifecycle return code is non-zero;
- report or binary output is absent;
- an `ERROR` identifier is present;
- any `WARNING` identifier is present;
- completion markers are absent;
- convergence metadata is absent or non-finite;
- percentage of steps not converging is not exact zero;
- the all-steps convergence marker is absent; or
- flow-routing continuity error is absent or non-finite.

W2 authorizes no warning allowlist. A warning requires repair, narrowing, or a
reviewed W2/B3 amendment; it is never ignored by string filtering.

### 15.2 Report bytes are not semantic identity

Human-readable reports contain wall-clock analysis timestamps and other
diagnostic prose. W2 records:

- the raw report SHA-256 as lineage evidence;
- normalized error/warning identifiers;
- normalized convergence fields; and
- the signed continuity value.

The report file itself is never part of the semantic output hash, a replay
contract, a promotion candidate, or runtime input.

## 16. Replay and hashing

### 16.1 Hash set

Each run records at least:

```text
canonical_request_sha256
member_content_id
case_content_id
rendered_input_sha256
pump_a_curve_sha256
pump_b_curve_sha256
engine_build_receipt_sha256
engine_executable_sha256
engine_solver_library_sha256
engine_output_library_sha256
raw_report_sha256
raw_binary_output_sha256
pump_setting_trace_sha256
semantic_output_sha256
```

W5 later defines the complete receipt and promotion lineage. W2 defines only
the generator-side identities needed to replay.

### 16.2 Semantic hash

```text
semantic_output_sha256 =
    sha256(
        "asw-0b4.semantic-output.v1\0"
        || canonical_semantic_bytes
    )
```

Canonical semantic bytes include:

- protocol, profile, member, case, and engine content identities;
- exact units and series-source identities;
- exact expected period count and time grid;
- canonical binary32 or integer series values;
- normalized engine diagnostic facts; and
- explicit W2 non-promotion status.

They exclude all local and wall-clock fields.
They use the same canonical JSON byte profile as section 7.2.

### 16.3 Required replay

Every case executes twice in two independently absent workspaces. Replay passes
W2 only when:

- canonical request hashes match;
- rendered input hashes match;
- curve hashes match;
- setting-trace hashes match;
- raw binary output hashes match;
- semantic output hashes match;
- normalized diagnostics match; and
- exact case ordering matches.

Raw report hashes are expected to differ because of analysis timestamps and
are not compared for equality. A semantic mismatch always rejects even if raw
binary hashes match. Raw binary equality is replay evidence only; it does not
make `.out` bytes promotable or a runtime contract.

## 17. Workspace and artifact lifecycle

### 17.1 Fresh-workspace rule

The caller supplies a parent root that does not exist. The B5 generator creates
it once and creates each case/replay directory once. It never:

- deletes a workspace;
- overwrites an input, report, output, trace, semantic result, or receipt;
- reuses a partially populated directory;
- follows a symlink for a run artifact;
- places two artifact roles at the same path; or
- depends on current working directory for content identity.

A collision or stale artifact rejects.

### 17.2 Artifact classification

| Artifact | W2 class | Git | Promotion eligibility |
| --- | --- | --- | --- |
| Canonical research request | Research-private | Excluded | W5 decision only |
| Rendered `.inp` | Engine-private raw | Excluded | Never |
| Human-readable `.rpt` | Engine-private raw diagnostic | Excluded | Never |
| Binary `.out` | Engine-private raw | Excluded | Never |
| Console and solver logs | Engine-private raw | Excluded | Never |
| Pump setting trace | Certification-private candidate | Excluded | W5 decision only |
| Canonical semantic result | Research-private candidate | Excluded until B5 review | Individual allowlisted fields only after W3/W4/W5 |
| Generator run record | Research-private | Excluded until W5 specification | Never by path coincidence |
| Vendor source/build/install trees | Engine-private | Excluded | Never |
| Executable and libraries | Engine-private | Excluded | Never |

No raw artifact becomes promotable because it is deterministic,
content-addressed, useful for debugging, or consumed by another research step.

## 18. Conceptual examples

These examples illustrate W2 meaning. They contain ellipses and explanatory
labels and are intentionally invalid as executable schemas.

### 18.1 Request example

```json
{
  "authority": {
    "protocol": "asw-0b4.generator-protocol.v2",
    "profile": "AU-NSW-LH-SYN-SPS-v1",
    "w1_sha256": "337aeab9465a8a1801b67c2ab0b408a2a2f07becddffc4a02161b64e6a8630de",
    "scope": "research-only",
    "promotable": false
  },
  "member": {
    "member_content_id": "<recomputed>",
    "parameters": {
      "well.D_w": {"value": "3.10", "unit": "m"},
      "...": "all W1 identities exactly once"
    }
  },
  "case": {
    "case_id": "G21_OBSTRUCTION_TRIGGER",
    "active_assignment": "pump-a",
    "control_mode": "forced-on",
    "mechanism_state": {
      "pump-a": {"obstruction": "0.75", "clearance-loss": "0"},
      "pump-b": {"obstruction": "0", "clearance-loss": "0"}
    },
    "inflow_stimulus": "constant-assessment",
    "horizon_s": 120
  },
  "engine": {
    "version": "5.2.4",
    "commit": "7952ca837988b1c32f791812eccc9fd64547e093",
    "...": "exact build identities"
  },
  "outputs": ["<exact section 13 ordered allowlist>"]
}
```

### 18.2 Semantic result example

```json
{
  "status": "candidate-only",
  "case_content_id": "<sha256>",
  "period_count": 120,
  "series": {
    "wet_well_depth_m": {
      "unit": "m",
      "representation": "ieee754-binary32-be-hex",
      "values": ["<8 hex digits per period>"]
    },
    "pump_a_setting": {
      "unit": "1",
      "representation": "exact-integer",
      "values": [1, 1, 1]
    }
  },
  "diagnostics": {
    "errors": [],
    "warnings": [],
    "steps_not_converging_percent": "0.0",
    "flow_routing_continuity_error_percent": "<finite observed value>"
  },
  "promotable": false
}
```

The shortened arrays make the example invalid. B5 must implement the exact
protocol tables and validation order, not copy either example as a schema.

## 19. Implementation and test handoff to B5

W2 does not create executable research code. When B5 is authorized after all
of B4, the generator slice must use TDD with the real pinned engine boundary:

1. failing request-byte and exact-key tests;
2. failing W1 member and cross-constraint tests;
3. failing curve-materialization and quantization tests;
4. failing engine-identity and fresh-workspace tests;
5. real SWMM input rendering tests against original W1 cases;
6. real offline solver-step setting capture;
7. real output-API extraction;
8. real warning/error/convergence/period/element rejection;
9. real semantic canonicalization and hashing;
10. real two-workspace replay;
11. integration from canonical request through semantic result; and
12. an end-to-end run of the complete W2 catalogue.

No mock SWMM, fallback solver, fabricated output, skipped real-engine gate, or
generator self-certification is permitted.

## 20. Handoff to B4-W3

W3 must define a separately executable certifier that consumes only:

- canonical W2 request bytes;
- materialized pump-curve bytes as candidate input evidence;
- allowlisted W2 semantic candidate bytes;
- normalized generator diagnostics; and
- exact content identities.

W3 must not:

- import the later generator package;
- call SWMM, the solver library, the output library, or report parser;
- trust generator membership, curve, period, unit, setting, or diagnostic
  assertions;
- read raw `.inp`, `.out`, `.rpt`, log, build, or workspace paths;
- use the generator's system-head, curve, volume, status, clock, or
  intervention helpers; or
- derive an expected value from generator output alone.

W3 must independently specify equations, numerical methods, limiting cases,
units, invariants, setting/flow consistency, full-pipe checks, mass balance,
operating points, clocks, transfer, interventions, ambiguity, and label
symmetry. W4 still owns all acceptance tolerances and sensitivity values.

If W3 cannot certify the semantic allowlist without a hidden common
implementation, W2 returns for repair rather than weakening the independence
boundary.

## 21. Explicit stop, repair, and return rules

W2 stops or returns when:

- the W1 family cannot be represented without a material physical change;
- SWMM requires an unowned physical parameter;
- the fixed-HGL/full-force-main mapping does not keep claim-critical periods
  inside the W1 envelope;
- a PUMP3 curve cannot preserve W1 monotonicity under the frozen
  materialization;
- the direct-inflow pattern cannot reproduce W1 volume input deterministically;
- exact pump settings cannot be aligned with official output periods;
- the engine emits a warning, error, missing diagnostic, or non-converging
  step;
- output shape, element identities, version, units, or periods drift;
- replay differs;
- an implementer must inspect a path or raw report to interpret semantic
  content;
- a certifier would need a generator helper or engine interface;
- raw artifacts would need promotion;
- a generator field has no named producer, consumer, authority, unit, and
  failure behavior; or
- a new physical, institutional, study, visibility, or runtime decision is
  needed.

Repair order:

1. correct a W2 derivation or mapping;
2. narrow the W2 case or output surface;
3. document an engine incompatibility and return to W1 for a material family
   change;
4. return to B3 for an engine-role or interface change;
5. return to B2 for a mechanism-form change; or
6. abandon the profile if the boundary cannot remain credible.

No repair may tune a W4 tolerance, hide a warning, infer a missing status from
flow alone, permit a stale workspace, or promote a raw solver artifact.

## 22. B4-W2 acceptance gate

| Requirement | Result |
| --- | --- |
| Exact predecessor binding | Pass |
| `B4-D12` explicit ruling | Pass: asymmetric offline generator decomposition |
| Canonical research input classes and scalar policy | Pass |
| Stable path-free content identities | Pass |
| Exact validation order and failure families | Pass |
| W1 wet well, inflow, pumps, levels, overflow, and force-main mapping | Pass |
| Mechanism states materialize as original PUMP3 curves | Pass |
| Solver settings frozen with independent derivation | Pass |
| Diagnostic case catalogue fixed without study history | Pass |
| Semantic output IDs, units, sources, and exclusions fixed | Pass |
| Pump settings captured without flow-only inference | Pass |
| Warning, error, convergence, period, unit, element, and shape failures fixed | Pass |
| Replay and semantic hashing fixed | Pass |
| Raw engine files and paths non-promotable by design | Pass |
| Independent-certifier responsibilities preserved | Pass |
| Production contract, code, generated member, or promotion created | No |
| `B4-D13` through `B4-D17` resolved | No; correctly deferred |

**B4-W2 is accepted for B4 protocol design. B4-W3 is the only next internal
work package. ASW-0B4, ASW-0B5, and all V-level gates remain open.**
