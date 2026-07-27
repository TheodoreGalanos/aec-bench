# ABOUTME: Freezes preregistered sensitivity probes, numerical tolerance formulas, and rejection rules for the first synthetic pump world.
# ABOUTME: Prevents post-output tuning while keeping generator, certifier, promotion, and production boundaries separate.

# AU-NSW-LH-SYN-SPS-v1 sensitivity, tolerance, and rejection protocol

## 1. Decision identity

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B4 — Generator and certification protocol` |
| Internal work package | `B4-W4 — Sensitivity, tolerance, and rejection protocol` |
| Protocol identity | `asw-0b4.sensitivity-tolerance-rejection-protocol.v1` |
| Composed check identity | `asw-0b4.composed-certification-checks.v1` |
| Protocol status | Accepted W4 research authority; not implemented, executed, certified, or promoted |
| Repository baseline | `5a98d8998568913d63e15ad5d624298117320aba` |
| Parent PRD SHA-256 | `56d6fe6a9c69796d819a1995ae63a85392ba85a4240df8baa87df99a76678335` |
| B1 claim/profile SHA-256 | `1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954` |
| B2 evidence/rights SHA-256 | `8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96` |
| B3 engine-role decision SHA-256 | `90603ddd481c0b627ad5e8ae5e0fc45f4c73b3910c86a8038cd80ce8eb80303d` |
| B3 compact verification SHA-256 | `db93443b31a197864709e7011af8a6aa15932cbec3260cf1a2afed735ffa3f11` |
| B4 plan SHA-256 | `fad8cb04fad9729a81466e4527e38bcf42cffcc11c940423f610b6ffb8d8118e` |
| W1 parameter/mechanism SHA-256 | `337aeab9465a8a1801b67c2ab0b408a2a2f07becddffc4a02161b64e6a8630de` |
| W2 generator-protocol SHA-256 | `66e96610b19920f93ddfa613a1f42e5d9bec6a4eb704905f82ce7b301961d130` |
| W3 independent-certification SHA-256 | `2b0b13a6f9facaf2f0e18f19a5d41069d8e5708a2df77b6dc6d6ed6c9ec65cde` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Decisions resolved here | `B4-D14 — Numerical tolerances`; `B4-D15 — Sensitivity region` |
| Next permitted internal package | `B4-W5 — Lineage and promotion protocol` only |

The identities bind this protocol to the repaired W2/W3 `v2` authorities. A
byte mismatch stops W4 composition. No implementation may substitute the
superseded `v1` horizon protocols, a nearby path, or an approximately matching
document.

## 2. Ruling

### 2.1 `B4-D14` numerical tolerances

`B4-D14` is **accepted, formula-derived and fail-closed**.

Every numerical comparison has:

1. an exact residual identity inherited from W3;
2. separately recorded representation, rendering, discretisation, reference
   method, and dynamic-settling allowances;
3. a deterministic formula evaluated from canonical inputs and independently
   calculated reference values;
4. a hard admissibility ceiling that the calculated allowance may not exceed;
   and
5. an exact rejection result when either the residual or its allowance exceeds
   the preregistered limit.

The tolerance is not a single percentage applied to all hydraulics. A larger
observed disagreement never enlarges a budget. An ill-conditioned member,
under-resolved case, or materially different engine consequence is rejected
or returned to its owning protocol.

### 2.2 `B4-D15` sensitivity region

`B4-D15` is **accepted, bounded and deterministic**.

The design contains:

- lower and upper one-at-a-time probes for every non-fixed W1 scalar;
- five fixed cross-parameter interaction probes;
- analytical boundary-proximity probes;
- exact observation, intervention, progression, and resource grids;
- fixed curve, time-step, report-step, and engine-sentinel perturbations; and
- a case-execution map that prevents an opaque Cartesian explosion.

There is no random search, fitted response surface, adaptive seed, or
candidate-output-driven expansion. Invalid probes remain recorded as
rejections; they are not replaced with more convenient values.

### 2.3 Maturity consequence

W4 adds one composed result state, `w4-checks-pass`, meaning only that one
candidate satisfied the W3 checks under this W4 protocol. It does not mean
`certified`, `V3`, `promotable`, benchmark-ready, or runtime-authorized. W5
still owns lineage and promotion specification. B5 still owns execution and
the actual family decision.

## 3. Authority and conflict order

The authority order is:

1. `asset-stewardship-worlds-prd.md`;
2. accepted B1 claim/profile;
3. accepted B2 evidence/rights pack;
4. accepted B3 engine-role decision and compact verification;
5. accepted B4 plan;
6. accepted W1 parameter/mechanism rulings;
7. repaired W2 generator protocol `v2`;
8. repaired W3 independent-certification protocol `v2`; and
9. this W4 protocol.

W4 may classify and bound a W3 residual. It may not:

- change a W1 value, bound, equation, mechanism, transition, observation, or
  claim;
- change a W2 case, duration, engine mapping, base setting, output, or byte
  representation;
- change a W3 equation, numerical method, dependency boundary, residual
  definition, or exact invariant;
- convert an exact W3 check into a tolerant one;
- use a W4 perturbation as a promotable base candidate;
- define W5 receipt serialization, promotion contents, or visibility classes;
- define ASW-0C histories, treatments, endpoints, or claims;
- define ASW-1 authority, obligation, handover, or persistence contracts; or
- create ASW-2 production placement or code.

If a required tolerance would mask an authority conflict, W4 stops and returns
to the owner. “The engine does that” is not a tolerance derivation.

## 4. Work-package and placement boundary

### 4.1 Allowed files

- `.gitignore`
- this sensitivity/tolerance/rejection protocol

### 4.2 Forbidden changes

This package creates no:

- executable sensitivity runner, generator, certifier, or receipt writer;
- generated request, curve, SWMM input, report, output, candidate, or family;
- file under `src/aec_bench`;
- production schema, contract, registry, CLI, Harbor, harness, provider,
  evaluator, persistence, or task-world implementation;
- amendment to W1, W2, W3, B3, or the parent PRD;
- copied tolerance from B3, the external prototype, SWMM examples, or a real
  utility criterion; or
- broad research unignore rule.

This record is a research implementation authority, not an importable schema
or runtime ABI. Future code must implement it deliberately and must not parse
the Markdown at runtime. Production code must continue to work with
`research/` physically absent.

## 5. Preregistration and anti-tuning rule

The complete W4 byte identity must be accepted before B5 creates the first W2
candidate for this profile. B5 records that identity in every composed check
result.

After the first candidate exists, none of the following may change under the
same W4 identity:

- a tolerance formula, term, coefficient, ceiling, denominator, window, or
  comparison direction;
- a sensitivity parameter, bound selector, member, case, or perturbation;
- a qualitative ordering;
- a boundary-proximity definition;
- a generation-level or family-level pass rule;
- an exclusion or ignored interval;
- the treatment of a failed or invalid probe; or
- the repair order.

A proposed change produces:

1. an immutable rejection of the affected attempt;
2. a written cause and owning-stage decision;
3. a new versioned protocol identity;
4. fresh generation identities; and
5. rerun of the complete affected design.

A result is never relabelled as calibration data and used to rescue itself.

## 6. Tolerance vocabulary and arithmetic

### 6.1 Exact checks

Exact checks have zero tolerance. They include W3 structural checks,
identities, hashes, units, keys, counts, labels, settings, clocks, state
transitions, period grids, G70 carry bytes, replay equality, intervention
isolation, and every exact invariant.

Binary floating-point values are not “approximately exact” merely because
they originated in one engine. Their allowed numerical difference must use a
formula below.

### 6.2 IEEE-754 representation bound

For finite normal binary32 `x`:

```text
ulp32(x) = 2^(floor(log2(abs(x))) - 23)
B32(x) = 0.5 ulp32(x)
```

For exact zero and binary32 subnormals:

```text
ulp32(x) = 2^-149
B32(x) = 2^-150
```

At an exact power-of-two boundary, the certifier uses the larger adjacent ULP
for a conservative outward bound. For a difference of independently encoded
values:

```text
B32_pair(x,y) = B32(x) + B32(y)
```

The original four bytes remain the identity source. `B32` is an error bound,
not permission to canonicalize non-canonical bytes.

### 6.3 Rendering bounds

W2 rendering gives:

```text
B_render_length = 0.5e-9 m
B_render_head = 0.5e-9 m
B_render_flow = 0.5e-9 m³/s
B_render_dimensionless = 0.5e-9
```

The flow value is the SI equivalent of half the `0.000001 L/s` rendering
quantum. Where the canonical decimal is already exactly representable at the
rendering precision, the actual bound is zero; the certifier proves that from
the bytes rather than assuming it.

### 6.4 Binary64 evaluation guard

For a direct analytical expression with result scale `x`:

```text
B64(x) = 32 ulp64(max(abs(x), unit_scale))
```

`unit_scale` is `1` in the canonical SI unit of the result. The factor `32`
is the fixed upper operation-count guard for the longest direct W1 scalar
expression, including friction-factor evaluation and outward summation. It
was selected before candidate output and is negligible relative to binary32
and curve-discretisation terms.

Every positive tolerance term and sum is rounded outward toward positive
infinity with binary64 `nextafter`. Overflow, underflow to zero, a non-finite
bound, or an unavailable ULP operation is a certifier internal error, not a
candidate pass.

### 6.5 Curve-discretisation bound

For the W1 quadratic pump curve and `N` equal flow segments, the maximum head
difference between the analytical curve and its chord interpolation is:

```text
B_curve_H(N,o,c) = H_0 A / (4 N²)

where A = 1 - a_o o - a_c c
```

At an independently solved root:

```text
S_F = abs(d(H_pump - H_system)/dQ)
B_curve_Q = B_curve_H / S_F
```

`S_F` is independently evaluated from the analytical equations. A non-finite,
zero, sign-inconsistent, or numerically unresolved slope rejects the member;
the certifier does not enlarge `B_curve_Q`.

Envelope witnesses, not acceptance fixtures:

| Curve segments | Maximum `B_curve_H` over W1 bounds |
| ---: | ---: |
| `16` | `0.01953125 m` |
| `32` | `0.0048828125 m` |
| `64` | `0.001220703125 m` |

The W2 base remains `N=32`. The other resolutions are W4 sensitivity probes
only.

### 6.6 Bisection and RK4 bounds

After W3's fixed 128 bisection iterations:

```text
B_root = max((Q_hi - Q_lo)/2, ulp64(Q_star))
```

For W3's `1 s` RK4 reference, the preregistered step-doubling estimate uses an
independent `0.5 s` reference:

```text
B_RK4_h(k) = (16/15) abs(h_RK4,1s(k) - h_RK4,0.5s(k))
B_RK4_Q(k) = (16/15) abs(Q_RK4,1s(k) - Q_RK4,0.5s(k))
```

The half-step reference is a W4 error estimator, not a replacement expected
trajectory. A non-decreasing error under the separate `2 s`, `1 s`, `0.5 s`
reference sequence rejects numerical convergence.

### 6.7 Dynamic-settling allowance

W3's reference is quasi-steady while W2 uses dynamic-wave routing. W4 keeps
that model difference separate from curve and representation error.

At an independently solved operating point:

```text
A_pipe = pi D² / 4
tau_hyd = L / (g A_pipe S_F)
r_hyd = 0.001
t_settle = ceil(-ln(r_hyd) tau_hyd / report_step) report_step
```

`r_hyd=0.001` is the preregistered maximum non-zero relative hydraulic
discrepancy after settling. It is one tenth of the W1 maximum magnitude of
flow-sensor bias and therefore prevents numerical/model allowance from
consuming the declared observation uncertainty.

For each running transition:

```text
B_dynamic_Q = r_hyd Q_star
B_dynamic_h,start = Q_star tau_hyd / A_w
```

The flow allowance applies only after `t_settle`. Before then, the candidate
must remain finite, non-negative, no greater than curve support plus
representation error, mass-balanced, and convergent toward the independent
operating point.

Each `B_dynamic_h,start` must not exceed the W2 conservative maximum
one-report-step level movement:

```text
Delta_h_step,max = 0.010068986195609708 m
```

The cumulative dynamic depth allowance through time `k` is the outward sum of
the allowances for starts completed by `k`. It must remain below one quarter
of the member's control hysteresis:

```text
sum(B_dynamic_h,start) <= 0.25 (h_start - h_stop)
```

If either ceiling fails, the member is too sensitive to the generator/reference
model difference and rejects. W4 does not add a larger transient tolerance.

### 6.8 Derived allowance and hard ceiling

For any numerical check:

```text
T_derived = outward_sum(
    representation terms,
    rendering terms,
    discretisation terms,
    reference-method terms,
    permitted dynamic term
)
```

The W3 residual is always retained and reported unchanged. Where a later
section defines a signed, preregistered numerical-method correction
`E_preregistered`, the comparison is:

```text
abs(residual - E_preregistered) <= T_derived
T_derived <= C_hard
```

Otherwise `E_preregistered` is exactly zero. The receipt records the raw
residual, correction, corrected remainder, derived allowance, and hard
ceiling separately. A correction is never inferred or fitted from candidate
numerical output.

The hard ceiling is never itself used as the tolerance. A budget that exceeds
its ceiling means the case is insufficiently conditioned or resolved.

For non-zero hydraulic quantities:

```text
C_flow_relative = 0.001 abs(Q_reference)
C_head_relative = 0.001 abs(H_reference)
```

For flow comparisons that affect an observation:

```text
C_flow_observation = 0.25 observation.flow_resolution
```

The applicable flow ceiling is the smaller non-zero ceiling. Off-state flow,
mass, trajectory depth, capability boundaries, and observations use their
specific rules below.

## 7. Denominators, windows, and comparison sets

### 7.1 Relative denominators

Relative values are reported with:

```text
D_Q = max(abs(Q_reference), Q_Re_min)
D_H = max(abs(H_reference), abs(z_d - h))
D_V = max(abs(V_reference), A_w observation.level_resolution)
```

where:

```text
Q_Re_min = Re_min pi D mu / (4 rho)
```

These denominators prevent division by zero. They do not convert a near-zero
check into a relative one; C-R13 remains absolute.

### 7.2 Interval classes

Every report interval receives exactly one class:

| Class | Meaning | Permitted comparisons |
| --- | --- | --- |
| `steady-eligible` | Running and beyond the current `t_settle` window | All applicable residuals |
| `settling` | Running but inside a preregistered start/transfer settling window | Exact, mass, curve, bounds, and convergence direction; no quasi-steady system/root pass |
| `control-edge` | Contains one independently reconstructed setting edge | Exact edge count, mass with edge quadrature, and C-R12 |
| `inflow-edge` | Contains one W1 inflow change | Exact inflow identity and mass with ramp quadrature |
| `stopped` | Setting zero outside an edge | Storage, mass, off-flow, and observation checks |

An interval cannot be silently dropped. If two classes apply, the more
restrictive treatment is recorded and every compatible check still runs.

### 7.3 Automatic-case edge alignment

Candidate and independent setting traces must have the same ordered edge
types and pump labels. Each matching edge may differ by at most one report
interval:

```text
abs(t_edge,candidate - t_edge,reference) <= report_step
```

No dynamic time warping, cycle deletion, many-to-one matching, or cumulative
phase reset is allowed.

## 8. Residual tolerance register

The W3 residual identity and definition remain unchanged.

| ID | W4 class | Preregistered tolerance or decision |
| --- | --- | --- |
| `C-R01` | Absolute plus cumulative | Pointwise storage budget in section 9.1; every sample plus signed cumulative bias must pass |
| `C-R02` | Signed-corrected absolute per interval | W3 residual unchanged; independently reconstructed right-end quadrature correction plus unexplained-error budget in section 9.2 |
| `C-R03` | Signed-corrected integral/cumulative | W3 prefix residual unchanged; signed quadrature prefix plus `0.05%` unexplained-error ceiling in section 9.3 |
| `C-R04` | Exact schedule plus absolute representation | Exact time/rate selection; rendered-flow plus binary32 budget only |
| `C-R05` | Absolute plus relative ceiling | Binary32 difference budget only; hidden junction/pipe storage is not tolerated |
| `C-R06` | Absolute analytical/curve plus relative ceiling | Head-pair, rendering, curve-chord, and binary64 terms |
| `C-R07` | Absolute analytical plus relative ceiling | Steady-eligible only; head-pair and independently enclosed system-render terms |
| `C-R08` | Absolute/relative | Steady-eligible only; root, curve, system, representation, and dynamic-flow terms |
| `C-R09` | One-sided | `capacity_fraction >= 1 - 16 ulp32(1)` at every running sample |
| `C-R10` | Pointwise plus integral trajectory | RK4, curve propagation, representation, and cumulative per-start dynamic-depth terms |
| `C-R11` | Pointwise plus integral trajectory | Steady-eligible only; root, RK4, representation, and residual dynamic-flow terms |
| `C-R12` | Temporal exact-window | Same ordered edges; at most one report interval difference |
| `C-R13` | Absolute near-zero | `B_render_flow + B32(Q)` |
| `C-R14` | Qualitative floor plus C-R08 | After settling, `Q >= Q_Re_min + T_C-R13`; inside settling, bounded convergence only |
| `C-R15` | Exact transformation plus pairwise numerical | Exact metadata/settings/edges; swapped series within outward sum of their own applicable budgets |
| `C-R16` | Exact | Exact carried binary32 bytes and carry hash; zero tolerance |
| `C-R17` | Exact boundary plus inherited numerical | Exact G70 structure/carry; C-R02/C-R10/C-R11 after the Pump B settling window; no extra allowance |
| `C-R18` | Interval classification with boundary margin | Capability interval and `1%` time margin in section 11.1 |
| `C-R19` | Exact state plus observation-separated response | Exact target-only state effect and at least three flow-resolution bins after uncertainty |
| `C-R20` | Exact visible equality | Exact equality under every preregistered matched flow quantizer probe |
| `C-R21` | Qualitative plus minimum separation | Post-clear response difference exceeds three coarsest applicable flow bins plus both numerical budgets |
| `C-R22` | Exact state plus qualitative/numerical ordering | Exact progression; monotone consequence; capable-to-ineligible transition with C-R18 margin; three-bin total flow loss |
| `C-R23` | Absolute percentage | Finite signed engine continuity error with `abs(error) <= 0.05%`; never substitutes for C-R02/C-R03 |
| `C-R24` | Exact | Exact two-workspace identities and semantic equality; zero tolerance |

`0.05%` is an original numerical-quality ceiling, not a utility or SWMM
acceptance criterion. It is half the `0.1%` non-zero hydraulic ceiling so
continuity error cannot consume the whole hydraulic comparison budget.

## 9. Storage and mass-balance budgets

### 9.1 C-R01 storage identity

For rendered diameter uncertainty:

```text
B_A =
    (pi/2) abs(D_w) B_render_length
    + (pi/4) B_render_length²
```

For sample `k`:

```text
T01,k =
    B32(V_k)
    + A_w B32(h_k)
    + abs(h_k) B_A
    + B_A B32(h_k)
    + B64(V_k)
```

Requirements:

```text
abs(r_volume,k) <= T01,k                  for every k
abs(sum(r_volume,k)) <= sum(T01,k)        for every prefix
```

A recurring one-sign bias is reported separately even when both inequalities
pass. W5 later decides whether compact evidence enters lineage; W4 does not
promote the series.

### 9.2 C-R02 one-step mass balance

For interval `k`:

```text
B_storage_delta,k =
    A_w (B32(h_k) + B32(h_(k-1)))
    + abs(h_k - h_(k-1)) B_A
    + B64(A_w (h_k - h_(k-1)))

B_flow,k =
    dt (
        B32(Q_in,k)
        + B32(Q_A,k)
        + B32(Q_B,k)
        + B32(Q_overflow,k)
        + 4 B_render_flow
    )
```

The certifier then constructs a signed, candidate-independent estimate of the
right-end-rectangle defect. It runs the W1 reference at `1 s` and `0.5 s`;
the half-second trace is aggregated onto the exact report grid. For each
reference step size `s`:

```text
E_quad,s,k =
    A_w (h_reference,s,k - h_reference,s,k-1)
    - dt (
        Q_in,reference,s,k
        - Q_pumped,reference,s,k
        - Q_overflow,reference,s,k
    )
```

For an automatic case, the independent trace uses the candidate's exact
setting-edge label and timestamp only after C-R12 proves that the edge is an
allowed match. That discrete edge selection is recorded before the certifier
reads candidate depth, flow, volume, or continuity values. It is not
best-fit alignment: no edge may move within its accepted report interval, and
no additional phase adjustment is allowed.

The same reconstruction applies exact W1 inflow edges. Inside section 6.7's
settling window, its quadrature-only flow trace uses the fixed first-order
response:

```text
Q_settle(t) =
    Q_after
    + (Q_before - Q_after) exp(-(t - t_edge) / tau_hyd)
```

`Q_before` and `Q_after` are independently solved W1 operating flows for the
matched pre/post setting and state. This trace estimates only sampled
quadrature; it does not replace W3's quasi-steady expected trajectory or
certify SWMM dynamics. `tau_hyd` is the larger finite positive value from the
pre/post running points; when only one side is running, that side supplies the
value. Outside the settling window the trace uses `Q_after`.

The correction and its method allowance are:

```text
E_quad,k = E_quad,0.5s,k
B_quad,k =
    (16/15) abs(E_quad,1s,k - E_quad,0.5s,k)
    + B64(E_quad,k)
```

The separate `2 s`, `1 s`, `0.5 s` sequence must show decreasing correction
error. An unresolved edge, two edges in one report interval, non-decreasing
error, or dependence on candidate numerical values rejects.

The unexplained-error allowance and its interval-scale ceiling are:

```text
T02,k =
    B_storage_delta,k
    + B_flow,k
    + B_quad,k

D_step,k = max(
    abs(A_w (h_reference,k - h_reference,k-1)),
    abs(dt Q_in,reference,k),
    abs(dt Q_pumped,reference,k),
    A_w observation.level_resolution
)

C02,k = 0.001 D_step,k
```

Both must hold:

```text
abs(r_mass,k - E_quad,k) <= T02,k
T02,k <= C02,k
```

The raw W3 `r_mass,k`, the signed correction, and the unexplained remainder
remain separate receipt fields. This prevents a large but predictable sampled
edge defect from becoming either hidden “continuity error” or a reusable
blanket tolerance.

### 9.3 C-R03 cumulative mass balance

For every prefix `n`:

```text
E_quad,prefix,n = sum(E_quad,k for k=1...n)
T03,derived,n =
    sum(
        B_storage_delta,k
        + B_flow,k
        + B_quad,k
        for k=1...n
    )

D_mass,n = max(
    V_work,
    sum(Q_in,k dt),
    sum((Q_A,k + Q_B,k) dt)
)

C_mass,n = 0.0005 D_mass,n
```

Both must hold:

```text
abs(R_mass,n - E_quad,prefix,n) <= T03,derived,n
T03,derived,n <= C_mass,n
```

The raw and corrected signed prefix series are both retained. Thus a
preregistered right-end sampling correction is auditable, while numerous
loose pointwise edge allowances cannot accumulate into an accepted biased
trajectory. Overflow volume, when non-zero, is included in the balance but is
never inferred from the engine continuity percentage.

### 9.4 C-R04 inflow

The independently constructed W1 value is rendered under W2 and correctly
rounded to binary32 before comparison:

```text
T04,k =
    B_render_flow
    + B32(Q_in,expected,k)
    + B64(Q_in,expected,k)
```

Wrong block, wrong edge second, interpolation across an unapproved interval,
or a correct numerical value at the wrong time is an exact rejection.

## 10. Hydraulic budgets

### 10.1 C-R05 force-main pump sum

```text
T05,k =
    B32(Q_force-main,k)
    + B32(Q_A,k)
    + B32(Q_B,k)
    + B64(Q_force-main,k)
```

The derived budget must also satisfy the non-zero `0.1%` relative ceiling when
a pump is running. W4 adds no transient, junction-storage, or hidden-pipe
storage allowance. If the W2 mapping has material unobserved storage between
the pumps and force-main output, the semantic allowlist is insufficient and
W2 returns for repair.

### 10.2 C-R06 pump head

```text
T06,k =
    B32(H_discharge,k)
    + B32(H_wet-well,k)
    + B_curve_H(32,o,c)
    + B_render_head
    + B64(H_pump)
```

This check runs for all finite positive pump flows, including settling. The
pump curve relates instantaneous head and flow even when the broader system
has not reached its quasi-steady root. A flow outside analytical support plus
render/representation budget rejects.

### 10.3 C-R07 system head

The certifier constructs outward input intervals for `z_d`, `h`, `L`, `D`,
`epsilon`, `K_minor`, `rho`, `mu`, `g`, and `Q` from the exact rendering and
binary32 bounds. It evaluates the W1 system equation over every interval
corner needed to enclose terms whose monotonicity has been proved. A term
without a proved sign or monotonicity is subdivided or bounded by interval
arithmetic; choosing convenient corners is an internal error.

```text
B_system_render,k =
    max(abs(H_system,corner - H_system,canonical))

T07,k =
    B32(H_discharge,k)
    + B32(H_wet-well,k)
    + B_system_render,k
    + B64(H_system)
```

C-R07 applies only to `steady-eligible` turbulent full-pipe samples. The
explicit W1 friction formula remains authority. A different SWMM
Darcy-Weisbach approximation is not silently absorbed beyond this bound.

### 10.4 C-R08 root flow

```text
B_system_Q,k = B_system_render,k / S_F

T08,k =
    B32(Q_candidate,k)
    + B_root
    + B_curve_Q(32,o,c)
    + B_system_Q,k
    + B_dynamic_Q
    + B64(Q_star)
```

The check applies only after `t_settle`. The derived budget must be no larger
than both:

```text
0.001 abs(Q_star)
0.25 observation.flow_resolution
```

Failure of the budget ceiling rejects the member before comparing the
candidate residual.

### 10.5 C-R09 full-pipe capacity

```text
T09 = 16 ulp32(1) = 0.0000019073486328125
```

At every running sample:

```text
1 - force_main_capacity_fraction <= T09
force_main_capacity_fraction <= 1 + B32(1)
```

The lower threshold is a 16-ULP representation guard at unity, not a physical
partial-full allowance. Capacity materially below full rejects the case and
the W2 force-main mapping.

## 11. Trajectory, capability, and intervention budgets

### 11.1 C-R10/C-R11 trajectories

For depth at `k`:

```text
B_curve_h,k =
    abs(
        h_RK4,analytical-curve,k
        - h_RK4,independent-piecewise-32,k
    )

B_dynamic_h,k =
    sum(B_dynamic_h,start for starts completed by k)

T10,k =
    B32(h_candidate,k)
    + B_RK4_h(k)
    + B_curve_h,k
    + B_dynamic_h,k
    + B64(h_reference,k)
```

For steady-eligible flow:

```text
T11,k =
    B32(Q_candidate,k)
    + B_RK4_Q(k)
    + B_curve_Q
    + B_root
    + B_dynamic_Q
    + B64(Q_reference,k)
```

Every point must pass. In addition:

```text
abs(sum(r_depth,k dt)) <= sum(T10,k dt)
abs(sum(r_flow,k dt)) <= sum(T11,k dt)
```

Each per-start dynamic depth term and its cumulative sum must satisfy section
6.7. C-R10 does not re-anchor the independent trajectory to candidate depth,
delete cycles, or align by best fit.

### 11.2 C-R18 capability margin

The certifier propagates the independently derived volume and flow bounds
through:

```text
t_draw = V_work / Q_net
Q_net = Q_star - Q_in_assess
```

using outward interval arithmetic. Let the resulting interval be:

```text
[t_draw,lo, t_draw,hi]
```

The preregistered time margin is:

```text
M_time = max(report_step, 0.01 t_draw_limit)
```

Classification is:

```text
capable:
    t_draw,hi <= t_draw_limit - M_time

review-eligible:
    t_draw,lo >= t_draw_limit + M_time

boundary-fragile:
    otherwise
```

For non-positive net flow, the propagated `Q_net` interval must be wholly
non-positive by:

```text
M_Q = max(4 B_Qnet, 0.001 Q_0)
```

An interval overlapping zero or either time-margin band is
`boundary-fragile` and rejects the member. It is not assigned the more useful
classification.

### 11.3 C-R19 intervention response

State isolation remains exact. A physically successful target intervention
must satisfy:

```text
M_flow_bins =
    3 observation.flow_resolution
    / (1 - abs(observation.flow_bias))

Delta_Q_target =
    Q_post - Q_pre

Delta_Q_target
    > T_Q,post + T_Q,pre
      + M_flow_bins
```

The denominator is positive under W1's exact bias bounds. The three-bin rule
makes improvement robust to both the complete allowed multiplicative-bias
range and quantization cell rather than merely positive in binary64. The same
requirement applies to anchor clearing histories A/B and the clearance repair.

For review, the W1 anchor analytical witnesses are:

| Relation | Independent anchor flow change |
| --- | ---: |
| G50 to G51 clearing | `+0.0047433193 m³/s` |
| G52 to G53 clearing | `+0.0018785737 m³/s` |
| G60 to G61 repair | `+0.0020305256 m³/s` |

The smallest is greater than the worst-case bias-adjusted three coarsest W1
flow bins (`0.0015151516 m³/s`).
These figures demonstrate that the preregistered margin is non-empty; B5 must
recompute them and must not use this rounded table as expected output.

### 11.4 C-R20/C-R21 ambiguity

The History A/History B pre-clear visible flow must be exactly equal under
each matched flow quantizer in the W4 observation grid.

After clearing:

```text
abs(Q_post,A - Q_post,B)
    > T_Q,post,A + T_Q,post,B
      + 3 max(flow_resolution_A, flow_resolution_B)
        / (1 - abs(matched_flow_bias))
```

The anchor analytical separation is approximately
`0.0028647470 m³/s`, greater than the worst-case bias-adjusted three coarsest
bins. Different lineage biases are not used to manufacture or destroy
ambiguity; a matched pair uses the same declared flow resolution and bias.

### 11.5 C-R22 no-maintenance consequence

At each G80 checkpoint:

- obstruction and clearance severity are recomputed exactly;
- neither severity may decrease;
- operating flow, capability margin, and head envelope may not improve;
- the first checkpoint must be `capable` with the C-R18 margin;
- at least one later checkpoint must be `review-eligible` with the C-R18
  margin; and
- first-to-last flow loss must exceed both numerical budgets plus the
  applicable `M_flow_bins`.

At the anchor, independent review values move from approximately `570.86 s`
drawdown to `2,932.74 s`; the capability transition occurs by the third
checkpoint. B5 recomputes these values from canonical rates.

## 12. Sensitivity design architecture

The design has four layers:

| Layer | Purpose | Engine use | Promotion eligibility |
| --- | --- | --- | --- |
| `OAT` | Exercise each non-fixed scalar at both bounds | None by default; independent analytical/certifier checks | Never as a probe merely by passing |
| `INT` | Expose cross-parameter hydraulic and mechanism interactions | Fixed case map | Accepted members may become B5 family candidates only after W5/B5 |
| `BND` | Exercise exact thresholds, ties, clipping, and invalid neighborhoods | None unless explicitly mapped | Never |
| `ENG` | Test curve, time-step, reporting, and sentinel dependence | Pinned SWMM diagnostic runs | Never; base W2 settings remain authority |

All probe identifiers and execution order are lexical ASCII order. Within one
probe, cases retain W2 lexical order. Replays are adjacent and ordered `0`,
then `1`.

## 13. One-at-a-time parameter probes

For each row below, create exactly:

```text
OAT.<parameter-id>.lower
OAT.<parameter-id>.upper
```

Only the selected parameter changes from the W1 anchor. The exact W1 bound is
used; no midpoint is added because the anchor is already the interior value.

| Group | Non-fixed parameter identities |
| --- | --- |
| Wet well | `well.D_w`, `well.h_stop`, `well.h_start`, `well.h_high`, `well.h_overflow` |
| System | `system.z_d`, `system.L`, `system.D`, `system.epsilon`, `system.K_minor` |
| Inflow | `inflow.Q_low`, `inflow.Q_nominal`, `inflow.Q_assess` |
| Pump | `pump.H_0`, `pump.Q_0` |
| Mechanism response | `mechanism.a_o`, `mechanism.b_o`, `mechanism.a_c`, `mechanism.b_c` |
| Mechanism progression | `mechanism.r_o_runtime`, `mechanism.r_o_start`, `mechanism.r_c_runtime` |
| Capability | `capability.t_draw_limit` |
| Observation | `observation.level_resolution`, `observation.level_bias`, `observation.flow_resolution`, `observation.flow_bias`, `observation.runtime_resolution` |
| Intervention | `intervention.e_clear`, `intervention.o_residual`, `intervention.e_repair`, `intervention.c_residual` |
| Resource | `resource.kit_lead`, `resource.access_duration` |

This is `34` parameters and `68` probes. Fixed constants, topology limits,
exposure maxima, pattern membership, inspection-band edges, kit availability,
and concurrency are tested exactly but do not receive fake lower/upper probes.

Every OAT probe runs:

- W1 membership and dimensional checks;
- analytical roots at `h_stop`, `h_start`, `h_high`, and `h_overflow`;
- capability and margin checks;
- all applicable qualitative orderings;
- progression/intervention/observation/resource checks when the selected
  parameter affects them; and
- no SWMM execution unless section 17 explicitly includes the probe.

A bound that violates a W1 cross-constraint is recorded
`probe-precondition-reject`. It is not clamped or replaced. A valid bound that
reverses a required ordering creates a family-level sensitivity rejection or
an explicit narrowing amendment.

## 14. Cross-parameter interaction probes

Unlisted parameters remain at anchor.

| ID | Bound selections | Purpose |
| --- | --- | --- |
| `INT.00.anchor` | All anchor values | Complete W2 case catalogue and reference |
| `INT.01.hydraulic-supporting` | `D_w=L`, `h_stop=U`, `h_start=L`, `h_high=L`, `h_overflow=L`; all inflows `L`; `z_d=L`, `L=L`, `D=U`, `epsilon=L`, `K_minor=L`; `H_0=U`, `Q_0=U` | Short working drawdown and strong clean capability |
| `INT.02.hydraulic-opposing` | `D_w=U`, `h_stop=L`, `h_start=U`, `h_high=U`, `h_overflow=U`; all inflows `U`; `z_d=U`, `L=U`, `D=L`, `epsilon=U`, `K_minor=U`; `H_0=L`, `Q_0=L` | Weak capability and operating-point/capability boundary stress |
| `INT.03.primary-dominant` | `a_o=U`, `b_o=U`, `r_o_runtime=U`, `r_o_start=U`; `a_c=L`, `b_c=L`, `r_c_runtime=L` | Strongest declared primary relative to secondary |
| `INT.04.secondary-dominant` | `a_o=L`, `b_o=L`, `r_o_runtime=L`, `r_o_start=L`; `a_c=U`, `b_c=U`, `r_c_runtime=U` | Direct falsification pressure on the primary/secondary ordering |

`L`, `A`, and `U` mean the exact W1 lower, anchor, and upper value. These are
probes, not an assertion that the W1 family is a full Cartesian product.

Each probe first runs W1 membership. An invalid interaction is retained as a
boundary result and does not execute SWMM. B5's accepted small family must
contain:

- `INT.00.anchor`;
- at least one valid non-anchor hydraulic interaction; and
- at least one valid non-anchor mechanism interaction.

If that minimum cannot be achieved without narrowing or changing W1, B4
returns for amendment rather than promoting an anchor-only family.

## 15. Boundary and semantic grids

### 15.1 Analytical boundary probes

| ID | Construction | Expected result |
| --- | --- | --- |
| `BND.00.forced-horizon` | W2 conservative `120 s` total exposure bound and the next integer second | `120 s` passes; a duration outside W2 rejects |
| `BND.01.root-endpoints` | Evaluate exact `F(0)`, `F(Q_support)`, and one manufactured endpoint-equality mutation | interior signs pass; equality rejects |
| `BND.02.reynolds` | Analytical flows immediately below, at, and above `Re_min` | below rejects; equality passes only because W1 explicitly accepts `Re >= Re_min`; above passes when all other root rules hold |
| `BND.03.capability-time` | Solve severity for `t_draw_limit - M_time`, inside the margin band, and `t_draw_limit + M_time` | capable, boundary-fragile, review-eligible |
| `BND.04.net-flow-zero` | Solve state for propagated `Q_net` wholly positive, overlapping zero, and wholly negative by `M_Q` | capable path, boundary-fragile, non-drawdown path |
| `BND.05.control-level` | Levels immediately below, exactly at, and immediately above each threshold under W3 ordering | one exact edge under the declared boundary rule |
| `BND.06.severity-clip` | Progression immediately below, exactly at, and beyond `0`/`1` before clipping | only declared clipping accepted |
| `BND.07.intervention-floor` | Each multiplicative branch below, equal to, and above its residual floor | exact `max` branch behavior |
| `BND.08.inspection-bands` | Exact lower boundary and adjacent values for `0.25` and `0.60` | lower-inclusive typed bands |
| `BND.09.full-pipe` | Capacity at pass threshold, one binary32 step above, and one below | pass/pass/reject under C-R09 |
| `BND.10.mass-sign` | Equal positive and negative residual magnitudes plus one-sign accumulated bias | symmetric magnitude handling; cumulative bias retained |

Manufactured invalid values are certifier fixtures, not W1 members or
generator cases.

### 15.2 Observation grid

Flow ambiguity uses the exact Cartesian grid:

```text
flow_resolution in {0.0001, 0.0002, 0.0005} m³/s
flow_bias in {-0.01, 0, +0.01}
```

Level quantization uses:

```text
level_resolution in {0.005, 0.01, 0.02} m
level_bias in {-0.01, 0, +0.01} m
```

Runtime uses:

```text
runtime_resolution in {60, 360, 900} s
```

Every grid uses W3 `ROUND_HALF_UP`, including exact half-bin fixtures. Paired
ambiguity histories always share one lineage setting. Opposing biases are not
assigned to the pair.

### 15.3 Progression and intervention grid

The exact matched levels are:

```text
progression = {all-lower, all-anchor, all-upper}
intervention = {least-effective, anchor, most-effective}
```

where:

```text
least-effective:
    e_clear=L, o_residual=U, e_repair=L, c_residual=U

most-effective:
    e_clear=U, o_residual=L, e_repair=U, c_residual=L
```

The primary-dominant and secondary-dominant interaction probes add the two
antagonistic mechanism corners. Exact clocks and no-cross-reset rules apply to
every grid member.

### 15.4 Resource grid

With `kit_initial=false` and `concurrent_limit=1` fixed:

```text
(kit_lead, access_duration) in {
    (lower, lower),
    (lower, upper),
    (anchor, anchor),
    (upper, lower),
    (upper, upper)
}
```

Every combination must remain positive and non-immediate. W4 checks clock and
constraint consequence only; ASW-0C still owns actual ordering time and access
windows.

## 16. Engine and numerical-method perturbations

These variants are diagnostic and non-promotable:

| ID | Change from W2 base | Purpose |
| --- | --- | --- |
| `ENG.00.base` | W2 `N=32`; routing/rule/report/wet/dry `1 s`; sentinel `0.0125` | Base candidate |
| `ENG.01.curve-16` | Pump curve `N=16` only | Coarse curve dependence |
| `ENG.02.curve-64` | Pump curve `N=64` only | Fine curve convergence |
| `ENG.03.report-2s` | Routing/rule/wet/dry remain `1 s`; report `2 s` | Reporting resolution |
| `ENG.04.route-report-2s` | Routing/rule/report/wet/dry all `2 s` | Routing and reporting coarsening |
| `ENG.05.sentinel-low` | Engine-only Manning sentinel `0.0100` | Detect hidden non-full-pipe influence |
| `ENG.06.sentinel-high` | Engine-only Manning sentinel `0.0150` | Detect hidden non-full-pipe influence |

All other settings, engine identities, case bytes, and member values remain
matched. A sensitivity renderer may create these inputs only under the W4
diagnostic identity; none is a W2 base request or promotion candidate.

Acceptance rules:

- `N=32` and `N=64` results differ by no more than the outward sum of their
  analytical curve budgets and preserve every qualitative classification.
- `N=16` may use its larger analytical curve budget but may not reverse an
  ordering, edge type, capability class, or intervention conclusion.
- `ENG.03` and `ENG.04` preserve exact case duration, case meaning, edge
  ordering, capability class, and qualitative outcomes.
- reference RK4 errors decrease across `2 s`, `1 s`, `0.5 s`;
- either sentinel perturbation changes claim-critical hydraulic series by no
  more than pairwise binary32 representation budgets and keeps C-R09 passing;
  otherwise the W2 full-pipe mapping rejects; and
- every variant replays exactly in two fresh workspaces.

## 17. Fixed case-execution map

### 17.1 Interaction members

| Probe | W2 cases |
| --- | --- |
| `INT.00.anchor` | Complete G00 through G80 catalogue |
| `INT.01.hydraulic-supporting` | G10, G11, G12, G21, G31, G41, G70, G80 |
| `INT.02.hydraulic-opposing` | G10, G11, G12, G21, G31, G41, G70, G80 |
| `INT.03.primary-dominant` | G12, G20, G21, G22, G30, G31, G40, G41, G50, G51, G52, G53, G60, G61, G80 |
| `INT.04.secondary-dominant` | G12, G20, G21, G22, G30, G31, G40, G41, G50, G51, G52, G53, G60, G61, G80 |

An invalid interaction stops before engine execution but remains in the result
matrix.

### 17.2 Engine variants

Apply every applicable ENG variant to `INT.00.anchor` for:

```text
G10, G12, G21, G31, G41, G70
```

G10 exercises automatic control and the base inflow. G12 exercises the clean
root. G21/G31 separate mechanisms. G41 stresses low net drawdown. G70
exercises transfer and carry.

Curve variants do not apply to G00. Sentinel variants require a running
force-main interval. Report/routing variants preserve a complete exact
duration and derive their expected period count independently.

### 17.3 Repetition

Every engine execution, including a diagnostic variant, runs twice in fresh
workspaces. A replay mismatch rejects before numerical comparison.

No case is added because an earlier result looks surprising. An unresolved
surprise rejects or creates a later versioned protocol amendment.

## 18. Stable qualitative ordering register

Every accepted probe and applicable engine variant must preserve:

1. Clean capability is no worse than matched degraded capability.
2. Increasing obstruction at fixed clearance cannot improve pump head,
   operating flow, drawdown, or capability class.
3. Increasing clearance loss at fixed obstruction cannot improve those
   quantities.
4. Adding the second mechanism cannot improve the matched single-mechanism
   state.
5. The accepted “primary” claim remains true across the declared family:
   matched normalized obstruction progression is at least as consequential as
   matched clearance progression at the preregistered checkpoints.
6. No-maintenance progression moves from capable to review-eligible with the
   C-R18 margin and three-bin flow consequence.
7. Successful clearing improves obstruction response by the C-R19 margin and
   leaves clearance state exact.
8. Successful clearance repair improves clearance response by the C-R19
   margin and leaves obstruction exact.
9. No intervention resets clocks, maxima, findings, restrictions, verification
   need, or unrelated history.
10. Losing or restricting Pump A cannot increase station capacity.
11. Label swap changes labels only.
12. G70 transfers future exposure to Pump B without rewriting Pump A history.
13. The ambiguity pair retains equal visible current flow and different
    post-clear response under the complete matched observation grid.
14. Resource lower bounds remain non-immediate and upper bounds do not create
    new authority or scenario timing.
15. Engine resolution or sentinel perturbation cannot change a physical,
    capability, intervention, or ambiguity conclusion.

Equality is permitted only where the W1 relation says “cannot improve.”
Required meaningful consequences use the explicit margins in section 11.

Any reversal rejects the affected member. If reversal occurs in a valid bound
or required interaction probe, the declared family rejects or narrows through
an upstream amendment.

## 19. Generation-level decision and receipt

### 19.1 Ordered terminal states

| State | Meaning |
| --- | --- |
| `w4-input-reject` | W4 identity, W2/W3 result, member, case, or sensitivity role is missing or contradictory |
| `w4-exact-reject` | A W3 exact or structural check fails |
| `w4-budget-reject` | A derived tolerance is non-finite, exceeds its hard ceiling, or lacks a required term |
| `w4-numerical-reject` | A residual, or its explicitly corrected remainder where defined, exceeds its preregistered derived tolerance |
| `w4-qualitative-reject` | A required monotonicity, ordering, symmetry, intervention, ambiguity, or consequence relation fails |
| `w4-boundary-fragile` | Capability, root, net flow, quantization, or classification lies inside a preregistered uncertainty margin |
| `w4-replay-reject` | Either base or sensitivity replay differs |
| `w4-checks-pass` | All applicable W3/W4 checks pass for this one generation/case role |
| `w4-internal-error` | The W4 implementation cannot complete its own calculation deterministically |

Precedence is table order except that an internal error always remains an
internal error. `w4-checks-pass` is neither family acceptance nor
certification.

### 19.2 Conceptual receipt contents

The deterministic result records:

- exact W1/W2/W3/W4 identities;
- member, case, perturbation, and replay identities;
- terminal state and first failing ordered check;
- every applicable residual value;
- every applicable signed correction and corrected remainder;
- each tolerance term separately;
- the derived tolerance and hard ceiling;
- interval classes and excluded quasi-steady windows;
- capability intervals and margins;
- qualitative ordering outcomes;
- exact invalid mutation or boundary role when applicable;
- no local path or wall-clock identity; and
- exact `promotable=false`.

W5 owns the serialized receipt, file layout, visibility, and promotion
reference. This list is conceptual and must not be copied into production as a
schema.

## 20. Family-level decision and receipt

### 20.1 Ordered family states

| State | Meaning |
| --- | --- |
| `family-incomplete` | A required probe, case, replay, or sensitivity result is absent |
| `family-exact-reject` | Any required exact rule or identity fails |
| `family-member-reject` | Anchor or minimum non-anchor coverage cannot pass |
| `family-ordering-reject` | A required qualitative ordering reverses |
| `family-sensitivity-reject` | Curve, step, report, sentinel, observation, progression, intervention, or resource result is fragile |
| `family-boundary-reject` | Required accepted members cannot be separated from capability/numerical margins |
| `family-w4-checks-pass` | W4 result matrix is complete and no earlier family state applies |
| `family-internal-error` | Family aggregation cannot be reproduced deterministically |

This is a B5 execution result vocabulary preregistered by W4. The final state
does not issue a promotion manifest or V3 claim.

### 20.2 Minimum family coverage

Family readiness requires:

- anchor passes the complete W2 catalogue;
- at least one non-anchor hydraulic interaction passes its fixed map;
- at least one non-anchor mechanism interaction passes its fixed map;
- all 68 OAT probes have a deterministic pass or expected precondition
  rejection;
- every boundary probe produces its preregistered class;
- all observation/progression/intervention/resource grids are complete;
- all ENG variants and replays are complete;
- every W3 invalid mutation still rejects; and
- no accepted result depends on a relaxed or post-output tolerance.

An invalid probe is not automatically a family failure when W1 already defines
the relevant cross-constraint. An ordering reversal, missing required
coverage, or valid-member fragility is a failure.

## 21. Stop, repair, and narrowing rules

### 21.1 Immediate stops

Stop the affected attempt when:

- any authority hash or protocol identity differs;
- a tolerance term is missing, negative, non-finite, candidate-fitted, or
  evaluated with inward rounding;
- an exact check is treated numerically;
- a hard ceiling is used as the tolerance;
- a settling, edge, or stopped interval is silently omitted;
- a generator diagnostic replaces an independent residual;
- an engine variant becomes a base or promotion candidate;
- one failed probe is replaced with an unregistered probe;
- a qualitative reversal is called “small”;
- a family pass relies only on the anchor;
- a raw engine artifact, research path, or local path becomes authority; or
- a result claims certification, V3, operational validity, or real-world
  accuracy.

### 21.2 Repair order

The ordered repair path is:

1. correct an implementation error without changing protocol bytes;
2. reject and rerun the exact generation identity;
3. narrow an explicitly fragile member or bound through a W1/W4 amendment;
4. repair an insufficient semantic output or case through W2;
5. repair an independent equation or comparison through W3;
6. replace a mechanism through B2;
7. revisit the engine role through B3; or
8. abandon the profile if the construct survives only through weaker checks.

A later repair never edits an issued result in place.

### 21.3 Envelope narrowing

Narrowing is allowed only when:

- the failed region is identified by preregistered probes;
- the retained region still includes anchor and the minimum non-anchor
  coverage;
- the mechanism and ambiguity constructs remain meaningful;
- all parameter metadata, rights, claim ceilings, and cross-constraints are
  updated through their owner;
- the W4 protocol receives a new identity; and
- the complete affected matrix reruns.

Narrowing cannot discard a difficult case solely because it failed.

## 22. Implementation and TDD handoff to B5

Executable W4 work begins only after W5/W6 accept the complete B4 protocol and
B5 is authorized.

B5 implements this slice test-first:

1. failing ULP, rendering, outward-rounding, and hard-ceiling unit tests;
2. failing curve-bound, root-slope, RK4 step-doubling, and settling tests;
3. failing C-R01 through C-R24 tolerance-composition tests;
4. failing edge-classification and one-report-step alignment tests;
5. failing capability-margin and boundary-fragile tests;
6. failing three-bin intervention, ambiguity, and progression tests;
7. failing OAT/INT/BND/ENG catalogue completeness tests;
8. failing generation-state precedence tests;
9. failing family-aggregation and minimum-coverage tests;
10. integration with real W2 candidate bytes and W3 results;
11. real pinned-SWMM execution for every mapped base/ENG case;
12. independent-certifier execution with generator/SWMM physically absent;
13. exact two-workspace replay; and
14. end-to-end family aggregation from canonical inputs to the conceptual W4
    family state.

Unit, integration, and end-to-end evidence are all required. No mock solver,
fabricated semantic candidate, skipped engine gate, fitted tolerance, or
disabled failing probe is permitted.

Implementation artifacts remain research-side until W5/B5 issues an exact
promotion manifest. No file under `src/aec_bench` is authorized by W4.

## 23. Handoff to B4-W5

W5 receives:

- the exact W1/W2/W3/W4 identities;
- the fixed result-state vocabularies;
- the requirement to retain each tolerance term separately;
- the OAT/INT/BND/ENG identities and deterministic ordering;
- generation-level and family-level result references;
- exact non-promotion status;
- rejected-member and fragile-region retention requirements; and
- content identity independent of path.

W5 must define:

- canonical receipt bytes and hashes;
- evidence, rights, unit, transformation, assumption, and source mappings;
- public, actor-visible, host-private, certification-private, and
  holdout-sensitive classes;
- exact allowed promotion contents;
- unknown-file, unknown-field, rights, version, and hash failures;
- the promotion-manifest specification; and
- B3/B4/B5 retirement and research-path absence evidence.

W5 may serialize W4 meaning. It may not change a tolerance, omit a failed
probe, promote an ENG variant, or turn `family-w4-checks-pass` into V3.

## 24. B4-W4 acceptance gate

| Requirement | W4 decision |
| --- | --- |
| `B4-D14` numerical tolerances resolved | Pass: formula-derived with hard ceilings |
| `B4-D15` sensitivity region resolved | Pass: deterministic OAT/INT/BND/ENG design |
| All C-R01 through C-R24 classified | Pass |
| Representation and rendering separated | Pass |
| Curve discretisation derived analytically | Pass |
| RK4 error preregistered | Pass |
| Dynamic settling separately bounded | Pass |
| Mass pointwise and cumulative treatment frozen | Pass |
| Head/root/trajectory treatment frozen | Pass |
| Control/off/on/full-pipe treatment frozen | Pass |
| Capability margin frozen | Pass |
| Intervention and ambiguity margins frozen | Pass |
| Observation/progression/resource grids frozen | Pass |
| Engine curve/step/report/sentinel variants frozen | Pass |
| Generation and family rejection states frozen | Pass |
| Post-output tuning prohibited | Pass |
| W5 ownership preserved | Pass |
| No executable or production surface created | Pass |
| Candidate, family, B4, or V3 completed | No |

**W4 decision: accept `B4-D14` and `B4-D15`; open B4-W5 only.**

This decision means B5 can calculate pass/reject outcomes without inventing or
tuning a tolerance after seeing SWMM output. It does not say that any candidate
or family has passed those outcomes.
