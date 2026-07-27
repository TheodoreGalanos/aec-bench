# ABOUTME: Freezes the B4-W1 original hydraulic family and the primary and secondary mechanism rulings.
# ABOUTME: Defines synthetic physical semantics without generating a world or creating a production contract.

# AU-NSW-LH-SYN-SPS-v1 — Parameter family and mechanism rulings

## 1. Decision identity

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B4 — Generator and certification protocol` |
| Internal work package | `B4-W1 — Parameter family and mechanism rulings` |
| Status | **Accepted for B4 protocol design only** |
| Repository baseline | `dc203ecd9c311227b33e7f5a0f29dd578e506728` |
| Parent PRD SHA-256 | `56d6fe6a9c69796d819a1995ae63a85392ba85a4240df8baa87df99a76678335` |
| B1 claim/profile SHA-256 | `1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954` |
| B2 evidence/rights SHA-256 | `8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96` |
| B3 engine-role decision SHA-256 | `90603ddd481c0b627ad5e8ae5e0fc45f4c73b3910c86a8038cd80ce8eb80303d` |
| B4 execution-plan SHA-256 | `fad8cb04fad9729a81466e4527e38bcf42cffcc11c940423f610b6ffb8d8118e` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Next permitted internal package | `B4-W2 — Generator protocol` only |

This authority resolves only B4 decisions `B4-D01` through `B4-D11`. It does
not complete ASW-0B4, open ASW-0B5, generate a world-family member, or earn a
V-level.

## 2. Authority, maturity, and placement

The parent PRD and accepted B1–B3 records remain higher authority. This record
adds the exact original synthetic family and physical mechanism semantics that
those records assigned to B4.

The family is:

- original and fictional;
- deterministic;
- bounded rather than statistically representative;
- expressed in SI;
- supported at the mechanism-form and physical-identity level by the accepted
  B2 sources;
- numerically synthetic at every value and coefficient;
- not calibrated to a real pump, station, population, manufacturer, utility,
  failure rate, or maintenance regime; and
- not an operational, safety, compliance, design, or maintenance
  recommendation.

This file is research design authority, not a runtime ABI. Parameter labels,
equation labels, table layouts, and event-order descriptions are research
identifiers. Production code must later re-express only B5-promoted semantics
inside the approved asset-local package and must run with `research/`
physically absent.

## 3. Work-package boundary

### 3.1 Allowed files

- `.gitignore`
- this ruling record

### 3.2 Forbidden changes

B4-W1 does not change:

- `src/aec_bench`;
- the B3 spike or any predecessor authority;
- production contracts, exports, registries, CLI, Harbor, `TrialRecord`,
  harness, evaluation, provider, or runtime surfaces;
- generator or certifier source;
- SWMM inputs, outputs, reports, settings, or binaries;
- normative repository architecture documents; or
- scenario timing, institutional actions, authority, obligations, study
  treatments, endpoints, budgets, or claims.

## 4. Ruling summary

| Decision | Ruling | Scope and limitation |
| --- | --- | --- |
| `B4-D01` clean pump | **Accept** | One original fixed-speed quadratic head-flow family, shared label-symmetrically by Pump A and Pump B at clean state |
| `B4-D02` hydraulic base | **Accept** | Cylindrical wet well, water-like reference fluid, one force main, Darcy-Weisbach system curve, bounded deterministic inflow |
| `B4-D03` primary mechanism | **Accept, narrow** | Progressive normalized obstruction/ragging severity with an original synthetic head-curve transformation; no real blockage or rate claim |
| `B4-D04` secondary mechanism | **Accept, narrow** | Progressive normalized hydraulic-clearance-loss severity for a declared fictional internal clearance interface; no millimetre gap or wear-rate transfer |
| `B4-D05` exposure mapping | **Accept** | Obstruction advances by runtime and starts; clearance loss advances by runtime only |
| `B4-D06` calendar role | **Accept** | Calendar advances independently and governs elapsed constraints; it does not directly degrade either pump in `v1` |
| `B4-D07` transfer trigger | **Accept** | Physical eligibility is based on inability to complete a bounded drawdown within a synthetic capability limit |
| `B4-D08` transfer consequence | **Accept** | Pump B becomes sole duty when a later authorized transfer occurs; both pump histories and latent states persist |
| `B4-D09` observation model | **Accept, minimal** | Quantized level and flow plus exposure meters and typed inspection evidence; no efficiency, power, vibration, NPSH, or universal diagnosis |
| `B4-D10` intervention effects | **Accept, physical only** | Inspection changes evidence; clearing changes obstruction only; clearance repair changes clearance loss only; verification generates evidence |
| `B4-D11` resource constraint | **Accept, parameterized** | One unavailable-at-start repair kit with bounded calendar lead time plus a bounded access/outage duration; exact schedule remains ASW-0C |

Decisions `B4-D12` through `B4-D17` remain open under B4-W2 through B4-W6.

## 5. Evidence and rights basis

| Basis | Accepted contribution | What it does not authorize |
| --- | --- | --- |
| `N-001` | Regional coherence of a fictional wet-well, rising-main, duty/standby, storage, access, starts, and maintainability context | Hunter Water compliance, copied values, typicality, approval, or operational instruction |
| `N-002` | Regional coherence of a submersible wastewater pumping-station context and inspectable commissioning boundary | A copied design or construction requirement |
| `N-003` | SI quantity and unit authority | Numerical parameter or engineering applicability |
| `N-004` | Qualitative relevance of solids, rags, clogging, and abrasive grit | A current Lower Hunter rule, pump model, blockage law, or numerical rate |
| `P-001` | Static head, friction/minor losses, system curves, and pump/system intersection | Geometry, curve, operating range, or tolerance |
| `P-002` | General pump/system behavior, multiple-pump context, hydraulic power, and maintenance relevance | Wastewater calibration or parameter values |
| `P-003` | Obstruction can alter flow/head/power/efficiency in pump- and operating-point-dependent ways | Universal direction for every signal, a transferable curve, multiplier, progression law, or failure rate |
| `P-004` | Increased internal hydraulic clearance can reduce pump performance in a configuration containing that interface | A wastewater-pump geometry, gap value, wear rate, or transferred marine-pump result |
| B3 decision | Exact SWMM candidate capability and role boundary | B3 fixture values, paths, schemas, tolerances, or generated inputs |

Every selected profile value in this record is `S`-class original synthetic
material except the declared conventional constant `fluid.g`. Equations based
on conservation, system head, and operating-point intersection use the
accepted `P`-class principles. No `C`-class calibration input exists or is
implied.

All external source bytes remain `Cite-only` or `Excluded` according to B2.
This record contains repository-authored paraphrase, equations, and original
values only.

### 5.1 B4-W1 assumption and disposition register

| ID | Assumption or construction | Class and basis | Rights | Falsification or later owner |
| --- | --- | --- | --- | --- |
| `W1-A01` | A single-phase water-like reference fluid is adequate for the first bounded hydraulic family | `S`, constrained by `P-001`/`P-002` identities | `Redistributable` under the repository licence | Reject any candidate requiring solids transport, non-Newtonian behavior, entrained air, surge, or cavitation |
| `W1-A02` | One original quadratic head-flow curve is sufficient to represent each clean fictional fixed-speed pump | `S`, constrained by the `P-001`/`P-002` operating-point principle | `Redistributable` under the repository licence | W2/W3 must reject invalid shape or operating-point behavior |
| `W1-A03` | One cylindrical wet well and one turbulent full-pipe Darcy-Weisbach force main bound the first hydraulic base | `S` construction using `P-001` physical identities | `Redistributable` under the repository licence | Reject non-turbulent, non-finite, multi-branch, or broader-network cases |
| `W1-A04` | The original diagnostic inflow pattern is a useful engine and certification stimulus | `S` | `Redistributable` under the repository licence | W2 returns to W1 if documented engine behavior requires a change; ASW-0C remains owner of study history |
| `W1-A05` | Normalized obstruction can be represented by a deterministic exposure-driven synthetic curve transformation | `S`, mechanism form supported narrowly by `N-004`/`P-003` | `Redistributable` under the repository licence | W4 rejects the mechanism or narrows the envelope if capability or intervention orderings reverse |
| `W1-A06` | A fictional replaceable internal hydraulic-clearance interface makes normalized clearance loss applicable | `S`, mechanism form supported narrowly by `P-004` | `Redistributable` under the repository licence | Return to B2 if applicability requires a transferred real pump geometry, gap, or wear law |
| `W1-A07` | Linear bounded runtime/start accumulation is adequate as a constructed deterministic progression rule | `S` | `Redistributable` under the repository licence | No field-rate claim; W4 owns sensitivity and rejects assumption-fragile regions |
| `W1-A08` | Drawdown time at an original assessment inflow is a sufficient physical capability predicate | `S`, using conservation and operating-point principles | `Redistributable` under the repository licence | W3/W4 reject non-unique, unstable, or ordering-reversing behavior |
| `W1-A09` | Quantized level, flow, exposure meters, status, and typed inspection findings are the minimum physical observation family | `S` | `Redistributable` under the repository licence | B5 must demonstrate latent/observable separation; ASW-1 later owns actor information semantics |
| `W1-A10` | Clearing and clearance repair have bounded, mechanism-specific, history-preserving effects | `S` | `Redistributable` under the repository licence | W3/W4 reject cross-mechanism reset, history erasure, or non-improving applicable intervention |
| `W1-A11` | One repair kit, bounded lead time, bounded access duration, and one concurrent intervention are sufficient resource surfaces | `S` | `Redistributable` under the repository licence | B5 must show consequence; ASW-0C/ASW-1 own timing and authority |

## 6. Originality and no-copy audit

The family was constructed independently after reviewing the B1/B2 envelope.
It deliberately does not inherit either diagnostic predecessor:

| Surface | B3 diagnostic or supplied-report value | B4-W1 treatment |
| --- | --- | --- |
| Wet-well geometry | B3 uses a `2.0 m` diameter; the supplied report uses `12.0 m²` area | Original `3.10 m` diameter anchor and bounded family |
| Force-main length | B3 uses `100 m`; the supplied report uses `180 m` | Original `525 m` anchor and bounded family |
| Clean pump curve | B3 uses four disposable piecewise points; the supplied report uses a separate piecewise curve | Original normalized quadratic family |
| Inflow | B3 uses constant `5 L/s`; the supplied report uses a separate `6–24 L/s` schedule | Original bounded rates and one original `8 h` diagnostic pattern; no study schedule |
| Obstruction | The supplied report uses fixed flow-axis scale `0.72` | Original two-state head-curve transformation; `0.72` is absent |
| Clearance | External evidence reports equipment-specific millimetre clearances | Normalized synthetic severity only; no gap is copied or promoted |
| Tolerances | Both predecessors contain diagnostic tolerances | None selected in W1; B4-W4 owns tolerance derivation |

Coincidental overlap in a common unit or general physical form is not source
authority. The exact W1 values derive only from the declared original anchor,
bounds, equations, and acceptance constraints below.

## 7. Quantity and numerical policy

### 7.1 Canonical units

| Quantity | Canonical unit |
| --- | --- |
| Length, level, head, diameter, roughness | metre (`m`) |
| Area | square metre (`m²`) |
| Volume | cubic metre (`m³`) |
| Flow | cubic metre per second (`m³/s`) |
| Duration and calendar interval | second (`s`) |
| Runtime | second (`s`), presented as hours only with exact conversion |
| Dynamic viscosity | pascal second (`Pa·s`) |
| Density | kilogram per cubic metre (`kg/m³`) |
| Start count | integer count |
| Severity, coefficient, efficiency-like intervention fraction | dimensionless |

Presentation may include `L/s`, hours, or days beside the canonical value. The
canonical value remains authoritative.

### 7.2 Deterministic arithmetic policy

- Parameter records retain decimal source text and canonical SI value.
- Start counts are integers.
- Severity is bounded on the closed interval `[0, 1]`.
- Exact clipping occurs only where an equation declares `clip`.
- B4-W2 freezes canonical serialization and solver input precision.
- B4-W3 freezes independent numerical methods.
- B4-W4 derives comparison and residual tolerances.
- A rounded value printed in this record is explanatory; B5 must use the
  canonical declared parameter value and recompute every derived quantity.

### 7.3 Parameter identity and cross-cutting disposition

The symbolic names below are stable B4 research parameter identities. A later
serializer may use different field names, but it must preserve an explicit
one-to-one mapping rather than importing this Markdown layout as a schema.

| Namespace | Stable parameter identities |
| --- | --- |
| Fluid | `fluid.rho`, `fluid.mu`, `fluid.g` |
| Topology and controls | `topology.max_running_pumps`, `topology.transfer_limit`; control thresholds reference `well.h_start` and `well.h_stop` without aliases |
| Wet well | `well.D_w`, `well.h_stop`, `well.h_start`, `well.h_high`, `well.h_overflow` |
| System | `system.z_d`, `system.L`, `system.D`, `system.epsilon`, `system.K_minor`, `system.Re_min` |
| Inflow | `inflow.Q_low`, `inflow.Q_nominal`, `inflow.Q_assess`, `inflow.T_diagnostic`, `inflow.base_pattern` |
| Clean pump | `pump.H_0`, `pump.Q_0` |
| Mechanisms | `mechanism.severity_domain`, `mechanism.a_o`, `mechanism.b_o`, `mechanism.a_c`, `mechanism.b_c`, `mechanism.r_o_runtime`, `mechanism.r_o_start`, `mechanism.r_c_runtime` |
| Exposure | `exposure.calendar_max`, `exposure.runtime_max`, `exposure.starts_max` |
| Capability | `capability.t_draw_limit` |
| Observation | `observation.level_resolution`, `observation.level_bias`, `observation.flow_resolution`, `observation.flow_bias`, `observation.runtime_resolution`, `observation.inspection_band_edges` |
| Interventions | `intervention.e_clear`, `intervention.o_residual`, `intervention.e_repair`, `intervention.c_residual` |
| Resource | `resource.kit_initial`, `resource.kit_lead`, `resource.access_duration`, `resource.concurrent_limit` |

The following metadata applies to every identity above unless a parameter table
states a narrower rule:

| Required property | W1 disposition |
| --- | --- |
| Evidence class | The value and bounds are original `S`; `fluid.g` is the sole declared `N` constant. Accepted `N`/`P` sources constrain context, units, identities, and mechanism form only. |
| Rights class | `Redistributable` under the repository licence. No external numerical value, table, curve, drawing, or source byte is incorporated. |
| Derivation | Original anchor and inclusive bounds declared in the owning section; derived values must be recomputed from canonical inputs. |
| Sensitivity treatment | W4 must evaluate anchor, lower/upper bounded cases, boundary-proximity cases, and the cross-parameter combinations preregistered there. No anchor-only acceptance is permitted. |
| Claim ceiling | Synthetic V3 candidate only. No real-station, representative-population, compliance, reliability, failure-rate, life-prediction, operational, or maintenance-prescription claim. |
| Current visibility | `Research-private`. The declarations are review evidence, not actor observations or runtime authority. |
| Later visibility candidate | Physical parameters are `runtime-internal`; only observations explicitly emitted through section 13 may become actor-visible. ASW-1 and the promoted package own the exact projection. |
| B5 rejection behavior | Missing, unknown, duplicated, non-canonical, non-finite, out-of-bound, dimensionally invalid, or cross-constraint-failing input rejects before engine execution. No implicit default, clamp, or extrapolation is allowed. |

The observation rows describe configuration, not the emitted reading. An
emitted reading may be actor-visible later; its latent basis, fixed lineage
bias, mechanism state, progression coefficients, and unobserved physical
parameters do not become actor-visible by implication.

Composite identities such as `inflow.base_pattern`,
`mechanism.severity_domain`, and `observation.inspection_band_edges` own their
exact fixed members as a single canonical value. Mathematical constants and
literal exponents inside an equation belong to that named equation rather than
forming independently variable parameters.

## 8. Clean hydraulic family

### 8.1 Reference-fluid assumption

The first family uses a single-phase, water-like reference fluid:

| Parameter | Anchor | Family bounds | Class | Treatment |
| --- | ---: | ---: | --- | --- |
| Density `rho` | `1000 kg/m³` | fixed | `S` | Synthetic reference; not a wastewater density claim |
| Dynamic viscosity `mu` | `0.001 Pa·s` | fixed | `S` | Synthetic reference; no solids-rheology claim |
| Gravitational acceleration `g` | `9.80665 m/s²` | fixed | `N`/declared constant | Used consistently in both paths |

The family excludes multiphase flow, non-Newtonian rheology, entrained air,
water hammer, surge, cavitation, and solids transport. A B5 candidate leaving
the turbulent full-pipe quasi-steady envelope is rejected rather than
extrapolated.

### 8.2 Wet-well and control-level family

The wet well is cylindrical with invert datum `z = 0`.

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| Internal diameter `D_w` | `3.10 m` | `[2.80, 3.40] m` | `S` |
| Stop level `h_stop` | `0.75 m` | `[0.65, 0.85] m` | `S` |
| Duty start level `h_start` | `1.65 m` | `[1.50, 1.80] m` | `S` |
| High evidence level `h_high` | `2.35 m` | `[2.15, 2.55] m` | `S` |
| Overflow level `h_overflow` | `3.35 m` | `[3.10, 3.60] m` | `S` |

Required ordering is:

```text
0 < h_stop < h_start < h_high < h_overflow
```

Area and volume are:

```text
A_w = pi D_w² / 4
V(h) = A_w h
V_work = A_w (h_start - h_stop)
```

No level in this family is a copied utility criterion or an operational set
point.

### 8.3 Force-main and system family

The discharge boundary is represented by one fixed hydraulic-grade elevation
and one full circular force main.

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| Discharge hydraulic-grade elevation `z_d` | `8.40 m` | `[8.00, 8.80] m` | `S` |
| Force-main length `L` | `525 m` | `[450, 650] m` | `S` |
| Internal diameter `D` | `0.175 m` | `[0.160, 0.190] m` | `S` |
| Absolute roughness `epsilon` | `0.00012 m` | `[0.00006, 0.00020] m` | `S` |
| Lumped minor-loss coefficient `K_minor` | `4.5` | `[3.0, 6.0]` | `S` |

The system representation is frozen to the Darcy-Weisbach form in section 9.
No material, pipe class, valve arrangement, or Hunter Water design requirement
is inferred from the selected numbers.

### 8.4 Inflow family

W1 freezes rate bounds and one original diagnostic pattern, not a study
schedule:

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| Low inflow `Q_in_low` | `0.0050 m³/s` | `[0.0035, 0.0060] m³/s` | `S` |
| Nominal inflow `Q_in_nominal` | `0.0090 m³/s` | `[0.0070, 0.0110] m³/s` | `S` |
| Capability-assessment inflow `Q_in_assess` | `0.0155 m³/s` | `[0.0140, 0.0160] m³/s` | `S` |

Required ordering is:

```text
0 <= Q_in_low < Q_in_nominal < Q_in_assess
```

The one-shot diagnostic horizon is:

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| Diagnostic horizon `T_diagnostic` | `28,800 s` (`8 h`) | fixed | `S` |

For local diagnostic time `tau` on the half-open interval
`0 <= tau < T_diagnostic`, the base pattern is:

| Interval | Inflow |
| --- | --- |
| `0 <= tau < 5,400 s` | `Q_in_low` |
| `5,400 <= tau < 10,800 s` | `Q_in_nominal` |
| `10,800 <= tau < 14,400 s` | `Q_in_assess` |
| `14,400 <= tau < 21,600 s` | `Q_in_nominal` |
| `21,600 <= tau < 28,800 s` | `Q_in_low` |

The pattern is deliberately asymmetric and exercises every declared rate. It
is not periodic, stochastic, inferred from a catchment, or claimed to resemble
a real diurnal profile. B4-W2 may define additional constant diagnostic cases
inside the same rate bounds, but it must retain this base pattern or return to
W1 with a documented incompatibility. ASW-0C retains ownership of the exact
study history and calendar placement.

### 8.5 Clean pump family

Pump A and Pump B are identical at clean state. Each is a fictional fixed-speed
submersible centrifugal pump train represented by:

```text
H_clean(Q) = H_0 [1 - (Q / Q_0)²]
```

for:

```text
0 <= Q <= Q_0
```

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| Shutoff head `H_0` | `18.5 m` | `[17.0, 20.0] m` | `S` |
| Zero-head flow `Q_0` | `0.043 m³/s` | `[0.040, 0.046] m³/s` | `S` |

This curve is original and synthetic. It is not a commercial pump curve,
selection, warranty, test result, preferred operating region, or efficiency
curve.

The family intentionally excludes:

- pump, motor, and wire-to-water efficiency;
- shaft and electrical power;
- NPSHr and NPSH margin;
- variable speed;
- multiple impeller diameters;
- assist pumping;
- simultaneous Pump A/Pump B operation; and
- extrapolation beyond `Q_0`.

If a later task requires an excluded quantity, B4 returns to the appropriate
authority rather than inferring it from head-flow data.

### 8.6 Controls for hydraulic generation

The active duty pump starts on an upward crossing of `h_start` and stops on a
downward crossing of `h_stop`. At most one pump may run. Pump A is initially the
duty assignment and Pump B is initially standby; only the later single
authorized transfer can change that assignment.

W2 owns the exact initial diagnostic level, boundary-event precedence, routing
step, and reporting step. It may not introduce periodic alternation, load
sharing, assist operation, implicit authority, or a second transfer.

## 9. Hydraulic equations

### 9.1 Wet-well balance

For a constant-area well:

```text
dV/dt = Q_in - Q_pumped - Q_overflow
dV/dt = A_w dh/dt
```

Only the active duty pump may contribute `Q_pumped`. Overflow is zero below
`h_overflow` and explicitly accounted above it by the later generator
protocol.

### 9.2 System curve

At wet-well depth `h`:

```text
H_static(h) = z_d - h
v(Q) = 4Q / (pi D²)
Re(Q) = rho v D / mu
f(Q) = 0.25 / [log10(epsilon/(3.7D) + 5.74/Re^0.9)]²
H_system(Q, h) =
    H_static(h)
    + f(Q) (L/D) v(Q)²/(2g)
    + K_minor v(Q)²/(2g)
```

The explicit friction-factor expression is the B4 engineering approximation
for accepted turbulent full-pipe cases. B5 rejects `Re < 4000`, invalid
geometry, non-finite values, or cases outside the declared curve interval.

At `Q = 0`, velocity-dependent losses are exactly zero and:

```text
H_system(0, h) = H_static(h)
```

### 9.3 Operating point

The quasi-steady operating point is the unique root:

```text
H_pump(Q, state) = H_system(Q, h)
```

on the closed interval `[0, Q_0]`.

Because the accepted pump family is decreasing and the accepted system family
is increasing for positive flow, an accepted case must have one root. Zero
roots, multiple roots, a boundary root without declared treatment, or a root
outside the curve rejects the candidate.

## 10. Mechanism family

### 10.1 Shared severity semantics

Each pump has two independent latent severity coordinates:

```text
o_i in [0, 1]  # obstruction/ragging severity
c_i in [0, 1]  # hydraulic-clearance-loss severity
```

where `i` is Pump A or Pump B.

The coordinates are constructed response variables, not measured mass,
millimetres, probability, remaining life, or percent damage. `0` is the clean
family state. `1` is the upper constructed B4 state, not physical destruction
or universal failure.

The fictional pump configuration explicitly contains an internal replaceable
annular hydraulic-clearance interface. This internal feature remains an
attribute of each integrated pump train; it is not a third managed component.
The declaration establishes applicability of the mechanism form only. It does
not claim that a real wastewater pump has this geometry.

### 10.2 Combined pump curve

The two severities alter the original clean family through:

```text
H_pump(Q, o, c) =
    max(
        0,
        H_0 [
            (1 - a_o o - a_c c)
            - (1 + b_o o + b_c c) (Q/Q_0)²
        ]
    )
```

| Coefficient | Meaning inside this synthetic rule | Anchor | Inclusive bounds | Class |
| --- | --- | ---: | ---: | --- |
| `a_o` | Obstruction-associated intercept loss | `0.08` | `[0.06, 0.10]` | `S` |
| `b_o` | Obstruction-associated curve steepening | `1.20` | `[0.90, 1.50]` | `S` |
| `a_c` | Clearance-associated intercept loss | `0.18` | `[0.12, 0.22]` | `S` |
| `b_c` | Clearance-associated curve steepening | `0.20` | `[0.10, 0.30]` | `S` |

For non-negative severity and coefficients:

```text
H_pump(Q, o, c) <= H_clean(Q)
```

throughout the declared interval. Neither mechanism can improve the clean
capability envelope. The formula is an original falsifiable benchmark rule,
not an empirical blockage or clearance law.

### 10.3 Primary obstruction progression

Obstruction advances only while the pump is exposed through runtime or a
qualifying completed start:

```text
o_i,next =
    clip(
        o_i
        + r_o_runtime Delta_runtime_i
        + r_o_start Delta_starts_i,
        0,
        1
    )
```

| Parameter | Anchor | Inclusive bounds | Canonical unit | Class |
| --- | ---: | ---: | --- | --- |
| `r_o_runtime` | `6.944444444e-8` | `[4.166666667e-8, 9.722222222e-8]` | `s^-1` | `S` |
| `r_o_start` | `0.00015` | `[0.00008, 0.00022]` | per completed start | `S` |

The anchor runtime rate equals `0.00025 h^-1` for presentation only. The law
represents constructed exposure accumulation. It does not claim that rags
accumulate smoothly, that starts cause real blockage by this amount, or that
all pump designs respond monotonically.

Obstruction is the declared primary mechanism because, at the anchor
coefficients, it drives the capability threshold more strongly than clearance
loss and is directly tied to the wastewater-service evidence. B4-W4 must still
test the complete bounded family and reject any member that loses the intended
ordering.

### 10.4 Secondary clearance-loss progression

Clearance-loss severity advances with runtime only:

```text
c_i,next =
    clip(
        c_i + r_c_runtime Delta_runtime_i,
        0,
        1
    )
```

| Parameter | Anchor | Inclusive bounds | Canonical unit | Class |
| --- | ---: | ---: | --- | --- |
| `r_c_runtime` | `3.333333333e-8` | `[2.222222222e-8, 4.444444444e-8]` | `s^-1` | `S` |

The anchor equals `0.00012 h^-1` for presentation. No start-count term or
calendar-time term exists for clearance loss in `v1`.

This is accepted only as a bounded synthetic secondary mechanism. No
millimetre clearance, wear-ring abrasion rate, marine-pump result, inspection
limit, or maintenance threshold is transferred from `P-004`.

### 10.5 Exposure envelope

The mechanism family is valid only within:

| Exposure | Inclusive envelope |
| --- | ---: |
| Simulated calendar | `[0, 31,536,000] s` (`0–365 d`) |
| Per-pump runtime | `[0, 10,800,000] s` (`0–3000 h`) |
| Per-pump completed starts | `[0, 2000]` |

These are synthetic certification bounds, not service intervals or equipment
limits. B5 rejects any proposed member or case outside them.

## 11. Clock and transition ordering

### 11.1 Clock definitions

- Calendar time advances for the world on every positive interval.
- Pump runtime advances only for the pump in physical `running` state.
- Standby, isolated, unavailable, and stopped pumps gain no runtime.
- A completed start increments exactly once on a non-running to running edge
  that successfully establishes positive duty operation.
- A failed attempt, command, or transient status is not a completed start
  unless a later authority explicitly adds and defines that concept.
- Transfer changes which pump receives later runtime and starts; it never
  reallocates prior exposure.

Calendar, runtime, and starts are therefore non-redundant. Pump B can gain
calendar time while retaining zero runtime and zero starts before transfer.

### 11.2 Physical interval ordering

For a physical interval beginning at time `t`:

1. apply already-completed physical intervention effects effective at `t`;
2. resolve the declared physical duty assignment and pump availability;
3. increment a completed start for any pump entering sustained running state;
4. solve and integrate the hydraulic interval;
5. advance calendar and active-pump runtime;
6. update exposure-driven severities from the completed interval; and
7. generate end-of-interval observations from the resulting latent state.

Institutional authorization, scheduling, obligation, and action ordering are
not defined here. ASW-1 and ASW-2 must later bind authorized actions to these
physical effects without changing them silently.

## 12. Transfer physics and no-maintenance consequence

### 12.1 Capability predicate

Define:

```text
V_work = A_w (h_start - h_stop)
Q_star = operating point at h_start and current pump state
Q_net = Q_star - Q_in_assess
```

If `Q_net > 0`:

```text
t_draw = V_work / Q_net
```

Otherwise `t_draw` is unbounded.

The synthetic physical capability limit is:

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| `t_draw_limit` | `1200 s` | `[1000, 1500] s` | `S` |

A pump is physically eligible for transfer/restriction review when:

```text
Q_net <= 0
or
t_draw > t_draw_limit
or
no valid operating point exists
```

This is a benchmark capability predicate, not an alarm setting, controller
rule, design requirement, or operational instruction.

### 12.2 Transfer consequence

When a later authorized scenario invokes the one permitted A-to-B transfer:

- Pump A stops;
- Pump B becomes the sole duty pump;
- no simultaneous pumping occurs;
- future runtime, starts, and mechanism progression accrue to Pump B;
- Pump A retains `o_A`, `c_A`, runtime, starts, maxima, inspections, and
  intervention history;
- Pump B retains all of its prior standby history;
- the wet-well state is continuous; and
- future hydraulic intervals use Pump B's current curve.

B4-W1 defines the physical state change only. It does not authorize, schedule,
or score the transfer.

### 12.3 No-maintenance consequence

With continued duty exposure and no intervention:

- obstruction and clearance-loss severity cannot decrease;
- active-pump head capability cannot improve;
- operating flow and drawdown margin cannot improve solely due to either
  mechanism;
- the capability predicate can move from pass to fail;
- combined upper severity can make `Q_star <= Q_in_assess`, causing wet-well
  rise rather than drawdown; and
- loss of acceptable Pump A capability makes standby availability and transfer
  consequential.

This is the required meaningful physical consequence. B5 must demonstrate it
inside accepted members; W1 does not claim that it has passed AG-04.

## 13. Observation model

### 13.1 Minimum visible physical readings

The first family permits only:

| Observation | Anchor treatment | Inclusive family treatment | Visibility |
| --- | --- | --- | --- |
| Wet-well level | Quantize to `0.01 m`, zero anchor bias | Resolution `[0.005, 0.02] m`; fixed lineage bias `[-0.01, 0.01] m` | Actor-visible when current and valid |
| Active-pump flow | Quantize to `0.0002 m³/s`, zero anchor bias | Resolution `[0.0001, 0.0005] m³/s`; fixed lineage multiplicative bias `[-1%, 1%]` | Actor-visible when current and valid |
| Runtime meter | Quantize to `360 s` | Resolution `[60, 900] s` | Actor-visible with meter lineage |
| Completed starts | Exact integer | Exact integer | Actor-visible with meter lineage |
| Pump duty/standby/running status | Exact declared physical projection | No hidden inference from flow alone | Actor-visible |
| Inspection result | Typed severity band with completion time | Deterministic mapping below | Visible only after completed inspection |

Every reading carries sample time, age, validity, unit, and quality metadata in
later schemas. W1 does not define those schemas.

Power, current, efficiency, vibration, temperature, NPSH, seal alarms, and a
universal blockage diagnosis are excluded from `v1`. Their absence prevents
unsupported signals from becoming accidental evidence.

### 13.2 Inspection mapping

A completed obstruction inspection may report:

| Latent obstruction | Typed physical finding |
| --- | --- |
| `0 <= o < 0.25` | `no_material_confirmed` |
| `0.25 <= o < 0.60` | `material_present` |
| `0.60 <= o <= 1` | `substantial_material_present` |

A completed clearance inspection may report:

| Latent clearance loss | Typed physical finding |
| --- | --- |
| `0 <= c < 0.25` | `clearance_loss_low` |
| `0.25 <= c < 0.60` | `clearance_loss_moderate` |
| `0.60 <= c <= 1` | `clearance_loss_high` |

These are original benchmark bands, not real inspection criteria. An inspection
changes evidence, not latent state.

### 13.3 Latent/observable separation

Current flow is not a unique diagnosis because both severities alter the pump
curve. Quantization and fixed lineage bias add bounded observation ambiguity.

B5 must construct at least one pair with:

- the same visible current flow within the frozen observation representation;
- the same current duty/status projection;
- different `(o, c)` composition or retained exposure history; and
- different response to at least one physically applicable intervention or
  future exposure.

The pair must not hide current facts from both actors unfairly. ASW-0C and ASW-1
later decide which historical evidence and obligations are available through
each continuity carrier.

## 14. Physical intervention effects

### 14.1 Inspection

Inspection:

- generates the applicable typed finding;
- does not change `o`, `c`, clocks, duty, or hydraulic state; and
- does not prove successful repair or closure.

### 14.2 Obstruction clearing

On completion of a physically successful obstruction-clearing process:

```text
o_after = max(o_residual, (1 - e_clear) o_before)
c_after = c_before
```

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| Clearing effectiveness `e_clear` | `0.85` | `[0.70, 0.95]` | `S` |
| Residual floor `o_residual` | `0.02` | `[0.00, 0.08]` | `S` |

Clearing does not reset clearance loss, runtime, starts, calendar time,
historical maxima, prior findings, restrictions, or verification needs.

### 14.3 Clearance-related repair

On completion of a physically successful clearance repair:

```text
c_after = max(c_residual, (1 - e_repair) c_before)
o_after = o_before
```

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| Repair effectiveness `e_repair` | `0.90` | `[0.80, 0.98]` | `S` |
| Residual floor `c_residual` | `0.02` | `[0.00, 0.05]` | `S` |

Repair does not reset obstruction, runtime, starts, calendar time, historical
maxima, prior findings, restrictions, or verification needs.

### 14.4 Verification operation

A post-intervention verification operation:

- runs the applicable pump under a declared B4-W2 hydraulic case;
- produces new current observations and a comparison to the frozen physical
  acceptance case;
- changes evidence only; and
- cannot erase history or self-authorize institutional closure.

Exact action names, prerequisites, durations, authorities, and closure rules
remain later-stage decisions.

## 15. Resource and access family

The minimum consequential resource family is:

| Parameter | Anchor | Inclusive family bounds | Class |
| --- | ---: | ---: | --- |
| Clearance-repair kit initially available | `false` | fixed | `S` |
| Repair-kit calendar lead time | `1,209,600 s` (`14 d`) | `[604,800, 2,419,200] s` (`7–28 d`) | `S` |
| Required access/outage duration | `14,400 s` (`4 h`) | `[7,200, 28,800] s` (`2–8 h`) | `S` |
| Concurrent pump interventions | `1` | fixed | `S` |

The lead-time clock advances while Pump A or Pump B is running or stopped.
Runtime and starts do not advance for a pump isolated during intervention.

This is a bounded resource surface, not procurement advice, a crew model, or a
utility work-management simulation. ASW-0C owns the exact order date and access
window; ASW-1 owns authority and obligation semantics.

## 16. Cross-parameter acceptance rules

A parameter vector belongs to the candidate family only if all of the following
hold before SWMM execution:

1. Every parameter is finite, within its inclusive bound, correctly dimensioned,
   and traceable to this authority.
2. All level and inflow orderings hold.
3. `H_0 > H_static(h_stop)`.
4. The clean pump/system pair has exactly one operating point at `h_stop`,
   `h_start`, `h_high`, and `h_overflow`.
5. Every accepted operating point is inside `(0, Q_0)` and `Re >= 4000`.
6. The clean pump has `Q_star > Q_in_assess` at the capability-assessment
   condition.
7. The clean anchor or candidate completes the declared drawdown at or below
   `t_draw_limit`.
8. Clean Pump A and Pump B are label-symmetric.
9. At least one bounded degraded state crosses the capability predicate while
   the matched clean standby pump remains capable.
10. Increasing either severity at matched parameters cannot improve head at
    any declared flow.
11. Obstruction clearing cannot change clearance loss.
12. Clearance repair cannot change obstruction.
13. No intervention resets clocks or retained history.
14. At least one same-reading/different-history pair can be constructed inside
    the observation and mechanism envelope.
15. The resource lead time or access duration makes at least one otherwise
    feasible intervention non-immediate.

Failure rejects the parameter vector. B5 does not clamp, extrapolate, weaken a
check, or tune a coefficient to rescue it.

## 17. Analytical design witness

The anchor values were independently evaluated using the equations in sections
8–12. This proves only that the proposed bounded family is non-empty enough to
continue protocol design. It is not a SWMM result, B5 generation, certification
case, accepted world, tolerance source, or V-level pass.

### 17.1 Clean anchor

Derived anchor values:

| Quantity | Result |
| --- | ---: |
| Wet-well area | `7.547676 m²` |
| Working volume | `6.792909 m³` |
| Operating flow at `h_stop` | `0.0263155 m³/s` (`26.3155 L/s`) |
| Operating flow at `h_start` | `0.0273994 m³/s` (`27.3994 L/s`) |
| Operating head at `h_start` | `10.9887 m` |
| Operating-point Reynolds number at `h_start` | approximately `199,349` |
| Clean net flow at assessment inflow | `0.0118994 m³/s` |
| Clean drawdown time | approximately `570.9 s` |

The clean anchor is below the `1200 s` physical capability limit.

### 17.2 Mechanism witness

At the anchor geometry and coefficients:

| State `(o, c)` | Operating flow | Drawdown at assessment inflow | Predicate |
| --- | ---: | ---: | --- |
| `(0, 0)` | `27.3994 L/s` | `570.9 s` | capable |
| `(0.50, 0)` | `22.5048 L/s` | `969.7 s` | capable |
| `(0.75, 0)` | `20.7218 L/s` | `1300.9 s` | transfer/restriction review eligible |
| `(1.00, 0)` | `19.2141 L/s` | `1829.0 s` | transfer/restriction review eligible |
| `(0, 1.00)` | `21.7788 L/s` | `1081.9 s` | capable at anchor |
| `(0.50, 0.50)` | `20.2499 L/s` | `1430.1 s` | transfer/restriction review eligible |
| `(1.00, 1.00)` | `15.2230 L/s` | no drawdown at `15.5 L/s` inflow | level rises |

The witness preserves the primary/secondary ordering at the anchor but does not
prejudge B4-W4 sensitivity results.

### 17.3 Ambiguous-reading witness

Two distinct anchor states produce the same unquantized operating flow to the
shown precision:

| State | `(o, c)` | Current flow |
| --- | --- | ---: |
| History A | `(0.65, 0.10)` | `20.9711 L/s` |
| History B | `(0.25, 0.742300)` | `20.9711 L/s` |

After anchor obstruction clearing:

| State | Post-clear flow |
| --- | ---: |
| History A | `25.7144 L/s` |
| History B | `22.8496 L/s` |

The current hydraulic reading alone does not identify the mechanism
composition, and the physically applicable clearing response differs. B5 must
reconstruct and certify a paired case rather than treating these rounded
figures as a gold fixture.

## 18. Explicit exclusions and stop conditions

B4-W1 stops or returns to B2 if later review requires:

- a real pump, manufacturer curve, model-specific clearance, failure rate, or
  field-derived progression law;
- copied Hunter Water, utility, OEM, or paper values as profile authority;
- an electrical, seal, bearing, vibration, thermal, cavitation, surge,
  non-Newtonian, solids-transport, or multiphase mechanism;
- a third managed component;
- simultaneous duty/assist pumping;
- a source claiming that the synthetic coefficients represent observed
  population behavior;
- a physical action whose effect cannot be independently represented; or
- a family that survives only by weakening the clean-envelope, monotonicity,
  transfer, observation-ambiguity, or history-retention requirements.

The SWMM role is revisited through B3 if the generator cannot express the clean
base and bounded mechanism curves without undocumented behavior. The mechanism
is replaced through B2 if its form cannot remain credible under the declared
synthetic claim ceiling.

## 19. Handoff to B4-W2

B4-W2 must use this family to freeze the generator protocol. It must:

1. define canonical research input serialization for these values without
   making this file layout a runtime contract;
2. map wet-well, inflow, pump curves, one force main, levels, and overflow to
   pinned SWMM;
3. define how mechanism states materialize as pump curves;
4. freeze diagnostic case selection inside the family without selecting the
   later study history;
5. freeze solver settings and their derivations;
6. freeze the semantic output allowlist and units;
7. reject every cross-parameter failure before engine execution;
8. record engine warnings, errors, convergence, periods, and exact identities;
9. define deterministic replay and content-based identity; and
10. keep raw engine files, paths, research code, and reports outside any
    promotion candidate.

B4-W2 may narrow this family if real pinned-engine behavior exposes a
documented incompatibility. A material equation, mechanism, range, or claim
change returns to W1 through a separately reviewed revision.

## 20. B4-W1 acceptance gate

| Requirement | Result |
| --- | --- |
| Exact predecessor binding | Pass |
| One original clean pump/system/wet-well/inflow family | Pass |
| Original diagnostic inflow pattern and horizon | Pass; no study history selected |
| SI units and original value classification | Pass |
| Stable parameter identities and per-value disposition | Pass through section 7.3 defaults plus owning parameter tables |
| Assumption, source, rights, unit, and decision registers | Pass |
| Primary mechanism selected | Pass: normalized obstruction/ragging |
| Secondary mechanism selected with applicability | Pass: normalized clearance loss for a declared fictional interface |
| No external numerical transfer | Pass |
| Distinct calendar/runtime/start clocks | Pass |
| Physical transfer trigger and consequence | Pass |
| Latent/observable separation | Pass |
| Same-reading/different-history construction possible | Pass analytically; B5 demonstration still required |
| Physical intervention effects distinct and history-preserving | Pass |
| Consequential bounded resource constraint | Pass |
| Non-empty analytical anchor | Pass as design evidence only |
| Generator/certifier/runtime boundaries preserved | Pass |
| Production contract or generated world created | No |

**B4-W1 is accepted for B4 protocol design. B4-W2 is the only next internal
work package. ASW-0B4 and all V-level gates remain open.**
