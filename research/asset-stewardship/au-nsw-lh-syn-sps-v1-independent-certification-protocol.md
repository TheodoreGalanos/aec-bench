# ABOUTME: Defines the independent certifier boundary, calculations, invariants, reference cases, and rejection outcomes for the first synthetic pump world.
# ABOUTME: Keeps certification separate from SWMM generation and leaves numerical tolerances and sensitivities to the next B4 work package.

# AU-NSW-LH-SYN-SPS-v1 independent certification protocol

## 1. Decision identity

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B4 — Generator and certification protocol` |
| Internal work package | `B4-W3 — Independent certification protocol` |
| Protocol identity | `asw-0b4.independent-certification-protocol.v2` |
| Protocol status | Accepted W3 research authority; amended by the pre-W4 horizon repair; not implemented, executed, or certified |
| Repository baseline | `5c23c8cf2567dd08cded35207bfb2dd937c1b989` |
| Horizon-repair baseline | `eed52934b3fba5b17b9901df0d23a8120febcc0f` |
| Parent PRD SHA-256 | `56d6fe6a9c69796d819a1995ae63a85392ba85a4240df8baa87df99a76678335` |
| B1 claim/profile SHA-256 | `1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954` |
| B2 evidence/rights SHA-256 | `8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96` |
| B3 engine-role decision SHA-256 | `90603ddd481c0b627ad5e8ae5e0fc45f4c73b3910c86a8038cd80ce8eb80303d` |
| B3 compact verification SHA-256 | `db93443b31a197864709e7011af8a6aa15932cbec3260cf1a2afed735ffa3f11` |
| B4 plan SHA-256 | `fad8cb04fad9729a81466e4527e38bcf42cffcc11c940423f610b6ffb8d8118e` |
| W1 parameter/mechanism SHA-256 | `337aeab9465a8a1801b67c2ab0b408a2a2f07becddffc4a02161b64e6a8630de` |
| W2 generator-protocol SHA-256 | `66e96610b19920f93ddfa613a1f42e5d9bec6a4eb704905f82ce7b301961d130` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Decision resolved here | `B4-D13 — Independent calculation path` |
| Next permitted internal package | `B4-W4 — Sensitivity, tolerance, and rejection protocol` only |

These identities bind this protocol to exact predecessor bytes. Any mismatch
is a protocol-identity failure. A later correction to a predecessor requires
an explicit impact review and a new certification-protocol identity; an
implementation must not silently accept the nearest available file or a
path-local substitute.

### 1.1 Pre-W4 compatibility repair

W4 preflight review found that generator protocol `v1` could force a pump
beyond the positive-storage operating envelope: the clean anchor G12
assessment reaches zero depth at approximately second `1,146`, G70's clean
Pump B segment reaches zero at approximately local second `639`, and bounded
W1 combinations can reach zero sooner. W1 defines no dry-pump or starvation
physics, so the certifier cannot calculate an expected value there without
inventing a mechanism.

Generator protocol `v2` now bounds individual forced snapshots to `120 s`,
G70 to two `60 s` segments, and G80 to explicit `120 s` snapshots. Its
conservative derivation proves that the complete forced interval retains at
least `0.026372467... m` above `h_stop,max` across the full W1 envelope.

This amendment:

- advances the independent-certification protocol identity from `v1` to
  `v2`, as required for a corrected predecessor binding;
- binds the exact generator protocol `v2` bytes above;
- updates only duration, period, G70 sequence, and positive-storage
  precondition checks; and
- leaves the independent equations, numerical methods, residual definitions,
  dependency boundary, result states, and W4 ownership unchanged.

No SWMM or candidate output is used as the expected result. Certification
protocol `v1` remains historical review evidence but is not an allowed B5
certifier identity.

## 2. Ruling

`B4-D13` is **accepted and narrowed** to a separately executable,
independently implemented certifier with four properties:

1. it receives only the canonical W2 request, materialized curve evidence,
   allowlisted semantic candidate, normalized diagnostics, and content
   identities;
2. it re-parses, re-hashes, re-derives, and re-calculates claim-critical facts
   without generator or SWMM code;
3. it can reject a candidate on structural, exact, or qualitative grounds
   before any tolerance is available; and
4. it cannot certify a candidate until W4 supplies preregistered numerical
   tolerances and sensitivity rulings.

The certifier is not a second SWMM wrapper and is not a clone of the generator.
Its hydraulic reference is the W1 quasi-steady physical construction,
integrated by an independently specified fixed-step method. Disagreement
between this path and SWMM is evidence to classify in W4, not a reason to copy
SWMM behavior into the certifier.

This work package accepts the design of the independent path. It does not
claim that executable independence, a candidate run, a family member, V3, or
any AG gate has passed.

## 3. Authority and conflict order

The authority order is:

1. `asset-stewardship-worlds-prd.md`;
2. the accepted B1 claim/profile;
3. the accepted B2 evidence/rights pack;
4. the accepted B3 engine-role decision and compact verification;
5. the accepted B4 plan;
6. the accepted W1 parameter/mechanism rulings;
7. the accepted W2 generator protocol; and
8. this W3 certification protocol.

This file elaborates the W3 path only. It cannot:

- revise a W1 equation, parameter bound, mechanism, clock, intervention, or
  capability predicate;
- revise a W2 request, engine mapping, case catalogue, candidate allowlist,
  serialization, or hash;
- select a W4 tolerance, perturbation, sensitivity grid, or rejection
  threshold;
- select W5 promotion contents or visibility classes;
- select ASW-0C histories, scenario timing, treatments, endpoints, or claims;
- select ASW-1 action, authority, obligation, handover, or persistence
  contracts; or
- create an ASW-2 production interface.

If a conflict appears, the certifier must fail closed and the owning authority
must be repaired. Greater detail or later authorship does not give this file
permission to override an earlier accepted decision.

## 4. Work-package and placement boundary

### 4.1 Allowed files

- `.gitignore`
- this certification-protocol record

### 4.2 Forbidden changes

This package creates no:

- executable certifier or generator;
- generated request, curve, solver input, report, output, receipt, candidate,
  or family member;
- file under `src/aec_bench`;
- production test, schema, protocol, interface, registry, CLI, provider,
  harness, evaluator, persistence, or Harbor integration;
- change to W1, W2, B3, the parent PRD, or normative library guidance; or
- blanket unignore rule for research working files.

This Markdown file is a durable research authority. It is not an importable
schema or runtime ABI. Future code must implement its semantics deliberately
and must not parse this document at runtime.

## 5. Certification boundary

### 5.1 Required execution topology

In B5, the generator and certifier execute as different programs in different
fresh environments:

```text
canonical request
        |
        v
generator environment -- pinned SWMM --> candidate byte bundle
                                              |
                                  content-only transfer
                                              |
                                              v
                          independent certifier environment
                         -- W1 calculations, no SWMM -->
                                  certification result
```

The certifier environment must be constructible and executable with:

- no generator package;
- no B3 spike package;
- no SWMM executable, source, dynamic library, output library, report parser,
  or vendor build tree;
- no network access;
- no access to the generator workspace;
- no raw engine files; and
- no import path that can resolve generator or SWMM modules.

Environment separation is tested, not asserted. B5 must prove both the absence
of forbidden artifacts and successful certification-path execution in that
environment.

### 5.2 Permitted inputs

The certifier may receive only these content-addressed byte roles:

| Input role | Purpose | Trust treatment |
| --- | --- | --- |
| Canonical W2 request bytes | Proposed member, case, states, schedule, engine identity, and output request | Untrusted; independently parsed and validated |
| Materialized Pump A curve bytes | Evidence of what the generator sent to SWMM | Untrusted; independently parsed and compared with W1 |
| Materialized Pump B curve bytes | Evidence of what the generator sent to SWMM | Untrusted; independently parsed and compared with W1 |
| Canonical W2 semantic candidate bytes | Allowlisted hydraulic series and W2 metadata | Untrusted; independently parsed, decoded, and checked |
| Normalized generator diagnostics | Declared lifecycle, warning, convergence, and continuity facts | Untrusted evidence; never physical proof |
| Exact content identities | Expected hashes and predecessor bindings | Untrusted declarations; every computable hash is recomputed |

Each role is passed explicitly. The certifier does not discover files by
walking a run directory and does not infer a role from a filename, directory,
extension, modification time, or proximity to another artifact.

### 5.3 Prohibited inputs and access

The certifier must not read or receive:

- rendered `.inp`;
- binary `.out`;
- human-readable `.rpt`;
- raw console or engine log text;
- executable, library, source, object, build, install, vendor, cache, or
  workspace paths;
- generator-internal request objects, parsed objects, status objects, or
  in-memory callbacks;
- generator-computed operating points, curve fits, volumes, clocks,
  interventions, observations, or capability classifications;
- report tables or engine dates;
- a generator pass/fail assertion;
- an expected-value file derived only from generator output; or
- a serialized object whose meaning requires importing generator code.

The certifier may read its explicitly supplied input files. “No raw paths”
means no dependence on engine or generator workspace paths; it does not forbid
the caller from providing a file descriptor or path for one permitted byte
role. Every decision remains path-independent.

### 5.4 One-way authority

The generator can produce a candidate but cannot certify it. The certifier can
reject the candidate but cannot:

- repair or regenerate bytes;
- substitute a default;
- clamp a value;
- reorder a series;
- reinterpret a unit;
- discard a warning;
- tune a tolerance;
- alter a case;
- promote output; or
- authorize runtime use.

There is no callback from certifier to generator during one decision. A
rejection ends that attempt and requires a new content identity.

## 6. Independence matrix

Every common dependency is disclosed below. An implementation audit must
classify each actual dependency before B5 execution.

| Dependency or concept | Generator use | Certifier use | W3 disposition | Required independence evidence |
| --- | --- | --- | --- | --- |
| W1 and W2 authority bytes | Implements them | Implements them | Shared specification is required | Exact authority hashes recorded; no shared executable helper |
| Programming-language runtime | Executes generator | Executes certifier | Common runtime version is allowed | Separate environments and dependency inventories |
| Standard library | Serialization, hashing, process/file operations | Serialization, hashing, arithmetic, file operations | Allowed only for general-purpose primitives | Imported modules listed; no project helper hidden behind stdlib boundary |
| JSON grammar | Canonical W2 bytes | Independent parser and exact-key validation | Shared public syntax is allowed | Separate parsing implementation and malformed-byte tests |
| UTF-8 and Unicode code-point ordering | Canonical serialization | Independent canonical-byte reconstruction | Shared standard is allowed | Certifier recomputes bytes without generator serializer |
| SHA-256 algorithm | Content identities | Independent identity recomputation | Shared public algorithm is allowed | No generator hash wrapper or precomputed pass assertion |
| IEEE-754 binary32 format | Encodes semantic floats | Independently decodes bit patterns | Shared public representation is allowed | Decode and negative-zero tests independent of generator |
| IEEE-754 binary64 arithmetic | May be used before rendering | Certifier analytical and integration arithmetic | Allowed implementation primitive | Numerical path and operation order frozen here |
| Decimal arithmetic | Canonical parameter/rendering policy | Exact transition and observation arithmetic | Allowed general primitive | Separate context, parsing, and tie-rule tests |
| SI unit vocabulary | Emits declared units | Validates exact units and dimensions | Shared physical vocabulary is required | Independent allowlist and dimensional table |
| W1 pump/system equations | Materializes curves and engine model | Re-implements analytical equations | Shared mathematical authority; code sharing forbidden | Separate source files, dependency audit, analytical cases |
| Pump-curve point grid | Writes 33 PUMP3 points | Reconstructs expected 33 points | Shared W2 specification; code sharing forbidden | Independent computation from member and state |
| SWMM engine/source/libraries | Core offline hydraulic generator | None | Strictly forbidden in certifier | Absence scan and blocked import/process tests |
| SWMM output/report parser | Extracts candidate series | None | Strictly forbidden in certifier | Dependency inventory and executable-environment proof |
| Generator package | Owns candidate production | None | Strictly forbidden in certifier | Import-resolution failure and package absence |
| B3 spike code or fixtures | Predecessor evidence only | None | Strictly forbidden in certifier | Absence scan; no fixture hashes in certifier package |
| Root-solving code | Generator does not certify roots | Fixed bisection specified here | Shared helper forbidden | Certifier-owned implementation and analytical reference cases |
| Trajectory integration code | SWMM dynamic-wave solver | Fixed RK4 reference specified here | Independent by design | No solver library; method-level tests |
| Control/status logic | SWMM rules and W2 setting recorder | Independent state reconstruction | Shared helper forbidden | Edge, threshold, and label-mirror reference cases |
| Clock logic | Candidate metadata/setting trace | Independently derived from time and status | Shared helper forbidden | Starts/runtime/calendar reference cases |
| Mechanism progression | W1 state materialization | Independently recomputed | Shared helper forbidden | Exact Decimal transition cases |
| Intervention effects | W1 state materialization | Independently recomputed | Shared helper forbidden | Cross-mechanism non-reset mutation tests |
| Observation quantizer | Not a W2 hydraulic output transform | Independently specified here | Generator dependency is unnecessary and forbidden | Tie, bias, band-edge, and ambiguity tests |
| Test fixtures | Generator-specific cases may exist | Certifier-owned reference and mutation cases | Shared fixture files forbidden | Separate fixture inventories; candidate bytes may cross only as inputs |
| Tolerances | None selected in W2 | Applied only after W4 | Not yet available | W4 identity required before a numerical pass |

General-purpose libraries beyond the language standard library are prohibited
for the first certifier unless W3 is explicitly amended before implementation.
In particular, a hydraulic, optimization, root-finding, ODE, SWMM, EPANET,
array-comparison, or units package cannot enter indirectly as a convenience.
This is a deliberately small calculation surface; dependency opacity would
weaken rather than strengthen its independence.

## 7. Independent validation pipeline

The certifier executes the following ordered stages. A failure stops the
candidate; later stages do not rescue it.

| Order | Stage | Failure class |
| ---: | --- | --- |
| 1 | Verify protocol invocation, exact input-role cardinality, and byte availability | `certifier-input-reject` |
| 2 | Recompute every supplied content hash and predecessor binding | `structural-reject` |
| 3 | Parse canonical request bytes with exact W2 key, scalar, ordering, and encoding rules | `structural-reject` |
| 4 | Reconstruct canonical request bytes and require byte equality | `structural-reject` |
| 5 | Validate member completeness, bounds, units, dimensions, and W1 cross-constraints | `exact-reject` or `quantitative-pending-w4` as classified below |
| 6 | Reconstruct the W2 case definition and reject undeclared case variation | `exact-reject` |
| 7 | Parse both materialized curves and independently reconstruct every expected point | `exact-reject` or `quantitative-pending-w4` |
| 8 | Parse semantic candidate bytes, exact keys, units, representations, lengths, and identities | `structural-reject` |
| 9 | Independently decode binary32 values and reconstruct semantic canonical bytes and hash | `structural-reject` |
| 10 | Independently construct time, inflow, state, control, clock, transition, and observation references | `exact-reject`, `qualitative-reject`, or `quantitative-pending-w4` |
| 11 | Evaluate pointwise and cumulative hydraulic residuals | `quantitative-pending-w4` |
| 12 | Evaluate monotonicity, label symmetry, transfer, intervention, ambiguity, and no-maintenance relations | `exact-reject`, `qualitative-reject`, or `quantitative-pending-w4` |
| 13 | Validate normalized diagnostics without treating them as physical proof | `exact-reject` or `quantitative-pending-w4` |
| 14 | Emit a deterministic certification result with all checks and residual observations | Result only; never promotion |

The result records every check attempted before the first failure and the
first failing stage. It must not continue far enough to transform malformed
bytes into apparently meaningful engineering evidence.

## 8. Canonical parsing, hashing, and scalar rules

### 8.1 Byte validation

The certifier independently enforces the W2 canonical JSON profile:

- UTF-8 without a byte-order mark;
- exact top-level and nested key allowlists;
- Unicode code-point key ordering;
- no duplicate keys;
- no unknown or omitted required key;
- no insignificant whitespace beyond the W2 profile;
- one terminal line feed and no trailing bytes;
- exact decimal-string forms for physical scalars;
- exact integer forms for counts, settings, and time;
- no exponent, leading plus, decimal comma, `NaN`, infinity, or negative zero;
  and
- exact protocol and authority identities.

It parses the supplied bytes, constructs its own semantic representation, and
serializes that representation using certifier-owned code. The reconstructed
bytes must equal the supplied bytes exactly. Parsing success alone is not
canonical-byte proof.

### 8.2 Content identities

The certifier independently recomputes at least:

```text
canonical_request_sha256
member_content_id
case_content_id
pump_a_curve_sha256
pump_b_curve_sha256
semantic_output_sha256
```

It also checks every predecessor identity against section 1. It does not
recompute raw engine hashes because raw engine artifacts are outside its
boundary; it validates that exact engine identities required by W2 are bound
into the request and semantic candidate without treating their presence as
proof that the corresponding engine ran.

Hash formulas and domain-separation strings are copied from W2 as
specification text and independently implemented. A supplied hash is never
used as the expected value for the same bytes.

### 8.3 Binary32 decoding

For every floating candidate value, the certifier:

1. requires exactly eight lower-case hexadecimal characters;
2. decodes the four big-endian bytes without using generator code;
3. interprets them as IEEE-754 binary32;
4. rejects NaN and positive or negative infinity;
5. normalizes a negative-zero input to positive zero only for semantic-hash
   reconstruction, while separately recording that non-canonical input was
   observed and rejecting it;
6. converts the finite value to binary64 for calculations without decimal
   round-tripping; and
7. retains the original four bytes for identity checks.

Integer arrays are never coerced through floating point.

## 9. Unit and dimensional contract

The exact W2 candidate units are:

| Quantity class | Canonical unit |
| --- | --- |
| Time, horizon, reporting step, runtime, lead time, access duration | `s` |
| Depth, head, diameter, length, roughness | `m` |
| Area | `m²` |
| Volume | `m³` |
| Flow | `m³/s` |
| Dynamic viscosity | `Pa·s` |
| Density | `kg/m³` |
| Gravitational acceleration | `m/s²` |
| Runtime progression rate | `s^-1` |
| Start count | exact integer count |
| Per-start progression rate | per completed start |
| Severity, setting, coefficients, capacity fraction | dimensionless |

The certifier has its own exact unit table. It does not perform opportunistic
conversion based on a string it recognizes. The only candidate-series
conversion already represented in semantic bytes is W2's declared LPS to
`m³/s` transformation. A candidate that labels an LPS value as `m³/s`, uses
`L/s`, omits a unit, or includes a plausible but unlisted unit rejects.

Dimensional identities checked independently include:

```text
A_w = pi D_w^2 / 4                       [m²]
V = A_w h                                [m³]
v = 4Q / (pi D^2)                        [m/s]
Re = rho v D / mu                        [1]
H_loss = (f L/D + K_minor) v^2/(2g)      [m]
dV = (Q_in - Q_pumped - Q_overflow) dt   [m³]
```

No power calculation is permitted. W1 and W2 explicitly exclude efficiency,
shaft power, and electrical power, so a certifier must not create a
hydraulic-power “sanity check” that could later become accidental evidence.

## 10. Independent physical equations

The certifier implements the W1 equations directly from canonical member
values. It never fits an equation to candidate series or materialized curve
points.

### 10.1 Wet-well storage

```text
A_w = pi D_w² / 4
V(h) = A_w h
V_work = A_w (h_start - h_stop)
```

The volume relationship is linear for the accepted cylindrical well. Any
functional, conical, pyramidal, tabular, or hidden storage geometry rejects.

### 10.2 System curve

For `Q > 0`:

```text
H_static(h) = z_d - h
v(Q) = 4Q / (pi D²)
Re(Q) = rho v D / mu
f(Q) = 0.25 / [log10(epsilon/(3.7D) + 5.74/Re(Q)^0.9)]²
H_system(Q,h) =
    H_static(h)
    + f(Q) (L/D) v(Q)²/(2g)
    + K_minor v(Q)²/(2g)
```

At exact zero flow:

```text
v = 0
velocity-dependent losses = 0
H_system(0,h) = z_d - h
```

The zero-flow branch executes before any Reynolds-number or logarithm
calculation. Positive-flow operating points with `Re < 4000` reject; the
certifier does not extrapolate the turbulent approximation into another
regime.

### 10.3 Pump curve

For pump state `(o,c)`:

```text
A = 1 - a_o o - a_c c
B = 1 + b_o o + b_c c
H_pump(Q,o,c) =
    max(0, H_0 [A - B (Q/Q_0)²])
Q_support = Q_0 sqrt(A/B)
```

The certifier requires `A > 0`, `B > 0`, and `0 < Q_support <= Q_0`. It checks
the analytical curve, not the W2 piecewise-linear curve, for physical
monotonicity and capability.

### 10.4 Operating point

Define:

```text
F(Q;h,o,c) = H_pump(Q,o,c) - H_system(Q,h)
```

An interior unique root requires:

```text
F(0) > 0
F(Q_support) < 0
```

An exact endpoint equality is a boundary root and rejects unless a higher
authority later defines its treatment. The certifier confirms that `F` is
strictly decreasing over the accepted interval from the analytical equation
and member signs; it does not infer uniqueness merely because a solver
returned one value.

The independent root method is fixed bisection:

1. set `lo = 0`, `hi = Q_support`;
2. perform exactly `128` binary64 iterations;
3. set `mid = (lo + hi) / 2`;
4. if `F(mid) > 0`, set `lo = mid`; otherwise set `hi = mid`; and
5. return `(lo + hi) / 2`.

No Newton method, secant method, curve interpolation, SWMM convenience
function, generator helper, SciPy solver, or early convergence criterion is
allowed. Fixed iteration count prevents a candidate-dependent stop threshold
from becoming an undeclared tolerance.

### 10.5 Capability

At exact `h_start`:

```text
Q_star = independent operating point
Q_net = Q_star - Q_in_assess

if Q_net > 0:
    t_draw = V_work / Q_net
else:
    t_draw = unbounded
```

The physical review predicate is true when:

```text
Q_net <= 0
or t_draw > t_draw_limit
or no valid operating point exists
```

This calculation is a synthetic benchmark predicate. The certifier must not
label it an alarm, operational instruction, compliance test, or real transfer
criterion.

## 11. Independent numerical trajectory

### 11.1 Purpose and non-equivalence

The trajectory reference checks the candidate against W1 mass balance and
quasi-steady pump/system physics. It is intentionally not dynamically
equivalent to SWMM's routing engine. W4 must classify and bound the expected
method discrepancy before any candidate can pass numerically.

The reference uses:

- binary64 arithmetic;
- exact `1 s` intervals;
- classical fourth-order Runge-Kutta (`RK4`);
- the section 10 bisection at every RK stage for a running pump;
- piecewise-constant W1 inflow within each one-second interval;
- fixed pump state within an interval; and
- no adaptive time step or external numerical library.

Before integration, the certifier independently recomputes W2's conservative
forced-horizon bound from the canonical W1 member and complete family limits.
Each forced-on snapshot in G12 through G61 and each G80 checkpoint must have
exact horizon `120 s`. G70 must have two exact `60 s` segments and a `120 s`
complete sequence. G00 remains the declared pumps-off `3,600 s` boundary.
The independently bounded trajectory must remain above `h_stop` for the
complete forced-on interval. Failure is a case-construction rejection before
any candidate comparison or W4 tolerance is applied.

The rule prevents an engine-specific empty-storage behavior from becoming
hidden benchmark physics. If a later hydraulic assessment requires more time
than the bounded window, W2/W3 return for explicit repair rather than adding a
dry-well branch inside the certifier.

### 11.2 Hydraulic derivative

Below overflow:

```text
dh/dt = (Q_in - Q_pump) / A_w
```

where `Q_pump` is zero when stopped and is the independently solved operating
flow at the RK stage depth when running.

At `h_overflow`, a positive net inflow is assigned to overflow so depth does
not exceed the declared storage boundary:

```text
Q_overflow = max(0, Q_in - Q_pump)
dh/dt = 0 when Q_overflow > 0 at h_overflow
```

If the net derivative is negative, the state may move below the boundary and
overflow is zero. A computed depth below zero or above `h_overflow` after
boundary treatment is an invalid reference case.

### 11.3 RK4 update

For interval width `dt = 1 s` and derivative `g(h,state,inflow)`:

```text
k1 = g(h_n)
k2 = g(h_n + dt k1/2)
k3 = g(h_n + dt k2/2)
k4 = g(h_n + dt k3)
h_(n+1) = h_n + dt (k1 + 2k2 + 2k3 + k4)/6
```

The overflow boundary is applied at every intermediate stage and final update.
The initial level comes from the canonical case, never from the first
candidate output value.

### 11.4 Automatic control reconstruction

Forced cases use their declared setting for every interval. Automatic cases
use a certifier-owned boundary state machine:

1. Pump A or Pump B is the declared duty label; the other pump is off.
2. Initial running state is the W2 case state. G10 and G11 begin stopped at
   `h_stop`.
3. At an interval boundary, a stopped duty pump starts when the independently
   integrated level has reached or crossed `h_start` upward.
4. A running duty pump stops when the independently integrated level has
   reached or crossed `h_stop` downward.
5. The transition is applied before solving the next interval.
6. One state is held through that interval.
7. There is no assist, fractional setting, periodic alternation, or second
   transfer.

The independent trace is compared with candidate settings and flows. Exact
forced-mode and topology contradictions can reject in W3. Boundary timing,
candidate-versus-reference edge alignment, and near-zero flow consistency are
quantitative W4 checks because the SWMM and RK4 event treatments are not
assumed identical.

### 11.5 Candidate internal mass balance

For candidate end-of-second samples `k = 1...N`, with `h_0` and `V_0` taken
from the canonical case:

```text
Q_pumped,k = Q_A,k + Q_B,k

r_mass,k =
    A_w (h_k - h_(k-1))
    - dt (Q_in,k - Q_pumped,k - Q_overflow,k)

r_volume,k = V_k - A_w h_k

R_mass,n = sum(r_mass,k for k = 1...n)
```

This is a declared right-end-rectangle residual for the sampled candidate, not
the SWMM internal continuity calculation. W4 owns the allowed pointwise and
cumulative magnitudes and treatment of sign. The normalized engine continuity
diagnostic is recorded separately; it cannot replace this check.

## 12. Curve-evidence checks

The materialized curve is candidate evidence about the generator-to-engine
boundary. The certifier independently reconstructs for `j = 0...32`:

```text
Q_j = Q_support (1 - j/32)
H_j = H_0 [A - B (Q_j/Q_0)²]
```

It applies W2's exact rendering quantization with certifier-owned Decimal code,
including:

- exact zero head at `j = 0`;
- exact zero flow at `j = 32`;
- head in metres;
- flow in litres per second only inside the materialized engine curve;
- strictly increasing head after quantization;
- non-increasing flow after quantization;
- exactly `33` ordered points; and
- the exact W2 curve-byte grammar and content hash.

The following checks are exact:

- point count;
- order;
- endpoint zero representation;
- unit role;
- canonical byte format;
- label/state assignment;
- state-specific curve identity; and
- Pump A/Pump B byte equality for matched states.

Analytical-versus-piecewise operating-flow disagreement and curve-resolution
effects are W4 quantitative and sensitivity checks. The certifier never uses
the materialized point set to derive its analytical expected curve.

## 13. Residual and invariant register

W3 freezes the definitions and classifications below. A blank tolerance is
intentional: W4 must fill it before B5 implementation may emit a numerical
pass.

| ID | Check | Definition | W3 class | W4 requirement |
| --- | --- | --- | --- | --- |
| `C-R01` | Storage identity | `r_volume,k = V_k - A_w h_k` | Numerical | Absolute and cumulative treatment |
| `C-R02` | Step mass balance | `r_mass,k` from section 11.5 | Numerical | Absolute per-step treatment |
| `C-R03` | Cumulative mass balance | `R_mass,n` from section 11.5 | Numerical | Absolute/integral treatment |
| `C-R04` | Candidate inflow | Candidate minus independently constructed W1 schedule | Exact for time/rate selection; numerical for binary32 representation | Representation-aware treatment |
| `C-R05` | Pump sum | `Q_force-main - (Q_A + Q_B)` | Numerical | Absolute treatment |
| `C-R06` | Candidate pump head | `(H_discharge - H_wet-well) - H_pump(Q,state)` | Numerical | Absolute/relative treatment |
| `C-R07` | Candidate system head | `(H_discharge - H_wet-well) - H_system(Q,h)` | Numerical | Absolute/relative treatment |
| `C-R08` | Independent root flow | `Q_candidate - Q_star(h,state)` while running | Numerical | Absolute/relative treatment |
| `C-R09` | Full-pipe envelope | `1 - force_main_capacity_fraction` | Numerical plus qualitative full-pipe requirement | One-sided treatment |
| `C-R10` | Reference depth trajectory | `h_candidate - h_RK4` | Numerical | Pointwise and integral treatment |
| `C-R11` | Reference flow trajectory | `Q_candidate - Q_RK4` | Numerical | Pointwise and integral treatment |
| `C-R12` | Control edge | Candidate setting edge versus independent threshold crossing | Numerical/temporal | Allowed alignment window |
| `C-R13` | Off-state flow | Candidate active-link flow while setting is zero | Numerical | Near-zero treatment |
| `C-R14` | On-state flow | Candidate active-link flow while setting is one | Qualitative plus numerical | Positive-flow floor |
| `C-R15` | Label mirror | G10 A series minus label-swapped G11 B series, and conversely | Exact for metadata/settings; numerical for hydraulic series | Series treatment |
| `C-R16` | Carry continuity | G70 segment-B initial depth minus segment-A final depth | Exact binary32 carry identity | None; exact |
| `C-R17` | Transfer hydraulic continuity | First B interval versus carried W1 state | Numerical | Boundary treatment |
| `C-R18` | Capability | Candidate consequence versus independent `Q_star`, `Q_net`, `t_draw` | Qualitative classification plus numerical | Boundary margin |
| `C-R19` | Intervention delta | Pre/post series and independent post-state calculation | Exact state isolation; numerical hydraulic response | Response treatment |
| `C-R20` | Ambiguous visible flow | Independent quantized flow A versus B | Exact quantized equality | None at anchor; W4 perturbs |
| `C-R21` | Ambiguous response | Post-clear consequence A versus B | Qualitative ordering plus numerical separation | Minimum separation |
| `C-R22` | No-maintenance progression | Recomputed state and consequence at ordered checkpoints | Exact state arithmetic; qualitative monotonicity; numerical consequence | Boundary/order margins |
| `C-R23` | Engine continuity diagnostic | Supplied normalized signed percentage | Numerical evidence only | Preregistered threshold and sign treatment |
| `C-R24` | Replay identity | W2 content hashes and semantic equality when both replays are supplied | Exact | None; exact |

W4 may add a threshold or a sensitivity member but may not redefine a residual
after seeing candidate results. A required redefinition returns to W3 through
an explicit amendment.

## 14. Exact structural and physical invariants

These invariants do not wait for numerical tolerances:

1. There is exactly one cylindrical wet well and exactly Pump A and Pump B.
2. At most one pump setting is `1` at any report instant.
3. Every setting is exact integer `0` or `1`.
4. Time is the exact integer grid `1...expected_periods`.
5. Every required series exists exactly once, has the exact unit and
   representation, and has `expected_periods` values.
6. Every binary32 series value is finite and canonical.
7. Depth, volume, inflow, overflow, and pump flows are non-negative.
8. All W1 parameter bounds, ordering rules, and exposure envelopes hold.
9. Pump A and Pump B share clean parameters but retain separate states,
   histories, curves, and identities.
10. A forced-on case has exactly its selected pump on and the other off.
11. A forced-off case has both pumps off.
12. G70 contains exactly segment A then segment B, one transfer, one boundary,
    and no duplicate boundary period.
13. Intervention transitions affect only their declared mechanism coordinate.
14. No intervention resets calendar, runtime, starts, maxima, findings,
    restriction history, or verification need.
15. Mechanism progression clips only where W1 declares clipping.
16. A stopped or standby pump receives no runtime.
17. A start increments only on a non-running to sustained-running edge.
18. Transfer never reallocates prior runtime, starts, or mechanism exposure.
19. Inspection changes evidence only.
20. Resource-kit initial availability is false, lead time advances on calendar
    time, and concurrent intervention capacity is exactly one.
21. No excluded quantity, including power, appears in request or candidate
    output.
22. No institutional action, authority, obligation, score, handover, closure,
    or actor-visibility decision appears in the hydraulic candidate.
23. The candidate remains explicitly non-promotable at W3.
24. Every forced-case duration satisfies the preregistered conservative
    positive-storage bound before execution.

An invariant involving the magnitude of a floating value is exact only when
the invariant is representational or sign-based. Near-zero, equality of
independently calculated floats, and threshold proximity remain W4 decisions.

## 15. Mechanism, clock, and transition checks

### 15.1 Exact progression arithmetic

The certifier parses canonical decimal strings into an independently
configured Decimal context and evaluates:

```text
o_next =
    clip(
        o + r_o_runtime Delta_runtime + r_o_start Delta_starts,
        0,
        1
    )

c_next =
    clip(
        c + r_c_runtime Delta_runtime,
        0,
        1
    )
```

`Delta_runtime` is an exact integer second count and `Delta_starts` an exact
integer. The certifier does not copy rounded checkpoint severities from the
request. It recomputes them from the prior state and canonical coefficients.

Required qualitative relations are:

- severity remains within `[0,1]`;
- positive exposure cannot reduce either severity;
- starts affect obstruction only;
- runtime can affect both mechanisms;
- calendar alone affects neither mechanism in `v1`;
- obstruction and clearance loss cannot improve the analytical pump curve;
  and
- continued no-maintenance exposure cannot improve capability solely because
  of either mechanism.

### 15.2 Clock reconstruction

For each one-second interval:

- calendar increments by one;
- runtime increments by one only for the reconstructed running pump;
- the other pump runtime increments by zero;
- a completed start increments at the transition into positive sustained
  running;
- no start increments on a stop, standby interval, command without positive
  operation, or transfer history copy; and
- histories before the interval remain associated with their original pump.

Candidate setting traces are inputs to consistency checks, not the clock
oracle. The independent control/state trace supplies the expected clocks.
Where candidate and independent edge timing differ, W4's preregistered
alignment rule decides the numerical comparison; the certifier must not choose
whichever trace produces a more favorable clock.

### 15.3 Physical interval order

The independent state transition order is:

1. apply an already-completed physical intervention effective at the boundary;
2. resolve duty assignment and availability;
3. increment a completed start for entry into sustained running;
4. integrate the hydraulic interval;
5. advance calendar and active-pump runtime;
6. update severities from completed exposure; and
7. generate end-of-interval observations.

Changing this order changes the protocol identity. An implementation must not
move observation before progression, apply an intervention after the hydraulic
interval, or retrospectively allocate exposure.

## 16. Intervention checks

### 16.1 Inspection

The certifier verifies that inspection:

- maps the applicable latent state to the exact W1 typed band;
- records a completion time;
- changes no physical state, clock, duty, history, or hydraulic value; and
- does not create proof of repair or institutional closure.

Band boundaries are lower-inclusive:

```text
[0,0.25) -> low/no-material band
[0.25,0.60) -> moderate/material-present band
[0.60,1] -> high/substantial-material band
```

### 16.2 Obstruction clearing

The independently calculated transition is:

```text
o_after = max(o_residual, (1 - e_clear) o_before)
c_after = c_before
```

For the anchor ambiguity cases:

```text
G50 -> G51: o 0.65 -> 0.0975; c remains 0.10
G52 -> G53: o 0.25 -> 0.0375; c remains 0.742300
```

The certifier verifies state isolation exactly and then checks that the
analytical pump envelope and independently calculated hydraulic consequence do
not worsen solely because of successful clearing. W4 supplies the response
magnitude treatment.

### 16.3 Clearance repair

The independently calculated transition is:

```text
c_after = max(c_residual, (1 - e_repair) c_before)
o_after = o_before
```

For the anchor repair cases:

```text
G60 -> G61: c 0.50 -> 0.05; o remains 0.50
```

State isolation is exact. Hydraulic improvement is qualitative with a W4
response magnitude. The unavailable-at-start kit, calendar lead time, access
duration, and concurrency constraint remain intact; a successful physical
effect must not imply that the intervention was immediately available or
institutionally authorized.

### 16.4 Verification

A post-intervention verification run may create current hydraulic evidence. It
cannot:

- alter a latent mechanism;
- reset history;
- create a second intervention effect;
- prove institutional closure;
- convert candidate evidence into promotion; or
- bypass W4 and W5.

## 17. Transfer checks

G70 is certified as one ordered physical sequence, not two unrelated runs.
The certifier independently verifies:

1. segment A has Pump A forced on at `(o_A,c_A)=(0.75,0)` and Pump B off;
2. segment A has exactly `60` intervals;
3. segment B initial depth is the exact binary32 terminal depth from segment A
   and its carry hash matches those bytes;
4. the boundary appears once in the concatenated sequence;
5. segment B has Pump A off and clean Pump B forced on;
6. segment B has exactly `60` intervals;
7. sequence time is exact `1...120`;
8. there is no simultaneous operation or second transfer;
9. Pump A stops gaining runtime and starts after transfer;
10. Pump B retains standby history and gains only future exposure;
11. both pumps retain latent state, prior exposure, intervention history, and
    evidence history;
12. wet-well storage is continuous across the boundary; and
13. the post-transfer hydraulic calculation uses Pump B's current curve.

The exact depth carry is an identity check. The hydraulic behavior on each side
of the boundary remains subject to W4 numerical treatment. W3 does not infer
who authorized the transfer or when it occurs in the later study.

## 18. Observation and ambiguity checks

### 18.1 Independent quantizer

For non-negative physical values, the certifier uses Decimal
`ROUND_HALF_UP` after applying the declared bias:

```text
level_visible =
    resolution_level
    * round_half_up((level_true + level_bias) / resolution_level)

flow_visible =
    resolution_flow
    * round_half_up(
        (flow_true * (1 + flow_multiplicative_bias))
        / resolution_flow
      )

runtime_visible =
    resolution_runtime
    * round_half_up(runtime_true / resolution_runtime)
```

Completed starts remain exact integers. Duty/standby/running status is the
exact declared projection and is not inferred from flow alone. The quantizer
is a certification calculation, not a production observation schema. ASW-1
and the promoted package later own actor projection, sample age, validity, and
quality fields.

Tie behavior is frozen here so B5 cannot choose it after seeing an ambiguity
result. W4 varies only the already bounded resolution and bias parameters; it
does not change the tie rule.

### 18.2 Anchor ambiguity witness

The certifier reconstructs:

```text
History A: (o,c) = (0.65, 0.10)
History B: (o,c) = (0.25, 0.742300)
```

At matched `h_start`, assessment inflow, label, and status it must show:

- equal actor-visible current flow under the anchor flow quantizer;
- equal current duty/running projection;
- unequal latent mechanism composition; and
- unequal post-obstruction-clearing response.

The expected values come from the independent analytical calculation, not from
the rounded W1 witness table or generator output. G50/G52 provide candidate
pre-intervention evidence; G51/G53 provide candidate post-intervention
evidence. W4 defines the minimum post-clear response separation and tests
resolution/bias perturbations.

This check proves observation non-identifiability inside the fictional
construction. It does not justify hiding available historical evidence from
actors or claim that a real inspection cannot distinguish mechanisms.

## 19. Label symmetry

Label symmetry is a transformation, not just two similar test names:

```text
swap(
    pump-a <-> pump-b,
    duty-a <-> duty-b,
    pump_a_flow <-> pump_b_flow,
    pump_a_setting <-> pump_b_setting,
    pump-a state/history/curve identity <-> pump-b equivalents
)
```

All label-neutral member, well, system, inflow, diagnostic, and hydraulic
fields remain unchanged.

For G10/G11 the certifier requires:

- exact canonical case transformation under the swap;
- exact setting-trace transformation;
- exact matched curve bytes for equal states;
- equal period counts and time grids;
- equal normalized diagnostic categories; and
- hydraulically equal swapped series under W4's binary32-aware comparison.

The certifier rejects label-dependent equations, coefficients, tolerances,
case order, or special handling. Pump A's initial duty role is a scenario fact,
not a different physical pump family.

## 20. Analytical, limiting, and relational reference cases

The certifier implementation must own reference inputs derived directly from
W1/W2 authorities. Rounded values printed in W1 are review witnesses, not
expected fixtures.

| Reference ID | Source case | Independent purpose | Required relation |
| --- | --- | --- | --- |
| `C00_STATIC_STORAGE` | `G00_ZERO_STATIC` | Zero-inflow, pumps-off storage limit | Constant depth/volume; zero flow and overflow |
| `C10_CLEAN_A` | `G10_CLEAN_A_BASE` | Automatic clean duty and base inflow | W1 control/mass behavior |
| `C11_LABEL_MIRROR` | `G11_CLEAN_B_BASE` | Full A/B symmetry transform | Swapped equality |
| `C12_CLEAN_CAPABILITY` | `G12_CLEAN_ASSESS` | Interior root and capable anchor | `Q_net > 0`, `t_draw <= limit` |
| `C20_PRIMARY_INTERIOR` | `G20_OBSTRUCTION_HALF` | Primary mechanism interior | Lower capability than clean; valid root |
| `C21_PRIMARY_TRIGGER` | `G21_OBSTRUCTION_TRIGGER` | Trigger witness | Review predicate true at anchor |
| `C22_PRIMARY_UPPER` | `G22_OBSTRUCTION_UPPER` | Upper primary state | No improvement over C21 or clean |
| `C30_SECONDARY_INTERIOR` | `G30_CLEARANCE_HALF` | Secondary mechanism interior | Lower capability than clean; valid root |
| `C31_SECONDARY_UPPER` | `G31_CLEARANCE_UPPER` | Upper secondary state | No improvement over C30 or clean |
| `C40_COMBINED_INTERIOR` | `G40_COMBINED_HALF` | Combined state | No improvement over matched single mechanisms |
| `C41_NO_DRAWDOWN` | `G41_COMBINED_UPPER` | Limiting net-flow case | `Q_star <= Q_in_assess` at anchor witness |
| `C50_CLEARING_A` | `G50`/`G51` | Clearing state isolation and response | Only obstruction changes; response non-worsening |
| `C52_CLEARING_B` | `G52`/`G53` | Alternative composition | Same visible pre-flow, different post-clear response |
| `C60_REPAIR` | `G60`/`G61` | Repair state isolation and response | Only clearance changes; response non-worsening |
| `C70_TRANSFER` | `G70_TRANSFER` | Single transfer and continuity | One carry, one duty change, retained histories |
| `C80_NO_MAINTENANCE` | `G80_NO_MAINTENANCE` | Clock-driven progression | Exact severities and non-improving ordered consequence |
| `C90_ZERO_FLOW_BRANCH` | Certifier analytical only | Avoid invalid Reynolds/log evaluation | Static head exactly |
| `C91_ROOT_BRACKET` | Certifier analytical only | Interior-root existence and uniqueness | Opposite endpoint signs, monotone `F` |
| `C92_OBSERVATION_TIES` | Certifier analytical only | Quantizer boundary behavior | Exact `ROUND_HALF_UP` results |
| `C93_RESOURCE_CLOCK` | Certifier structural only | Distinguish calendar from runtime | Lead time advances while pump exposure need not |

Reference cases outside the W2 catalogue are certifier unit-level analytical
cases only. They are not new generator cases, family members, study histories,
or promotion candidates.

## 21. Deliberately invalid mutation catalogue

A certifier that accepts only clean inputs has not demonstrated rejection
power. B5 must apply each mutation to a valid content bundle, recompute only
the enclosing transport hash when required to reach the target validation
stage, and prove deterministic rejection.

| Mutation ID | Mutation | Expected first rejection |
| --- | --- | --- |
| `M01_HASH` | Change one byte without changing its declared hash | Content-hash mismatch |
| `M02_UNKNOWN_KEY` | Add an unknown request or semantic key | Exact-key failure |
| `M03_DUPLICATE_KEY` | Duplicate a JSON key | Canonical parse failure |
| `M04_NONCANONICAL_NUMBER` | Use exponent, plus sign, negative zero, or decimal comma | Scalar canonicalization failure |
| `M05_BAD_HEX` | Use uppercase, wrong length, NaN, infinity, or negative-zero binary32 hex | Representation failure |
| `M06_UNIT` | Replace one exact SI unit with a plausible alternative | Unit allowlist failure |
| `M07_PERIOD` | Remove, duplicate, or append a report period | Time/length failure |
| `M08_SERIES` | Remove a required series or add an excluded series | Semantic allowlist failure |
| `M09_CURVE_COUNT` | Use 32 or 34 materialized points | Curve structure failure |
| `M10_CURVE_ENDPOINT` | Make either required zero endpoint non-zero | Curve exact failure |
| `M11_CURVE_ORDER` | Swap adjacent materialized points | Curve order failure |
| `M12_LABEL_CURVE` | Give matched A/B states different curve bytes | Label symmetry failure |
| `M13_SIMULTANEOUS` | Set both pumps to `1` at one instant | Topology invariant |
| `M14_WRONG_DUTY` | Run the non-selected pump in a forced case | Duty-label invariant |
| `M15_OFF_FLOW` | Add material positive flow to an off pump | W4 off-flow residual rejection |
| `M16_VOLUME` | Corrupt one volume while preserving depth | Storage residual rejection |
| `M17_MASS` | Corrupt one inflow or flow sample | Mass residual rejection |
| `M18_CAPACITY` | Make force-main capacity materially non-full | Full-pipe rejection |
| `M19_CAPABILITY_GAIN` | Make greater severity improve head or operating flow | Monotonicity rejection |
| `M20_CLOCK_ERASE` | Reset runtime or starts after intervention | History-retention invariant |
| `M21_CROSS_RESET_CLEAR` | Clearing also reduces clearance loss | Intervention-isolation invariant |
| `M22_CROSS_RESET_REPAIR` | Repair also reduces obstruction | Intervention-isolation invariant |
| `M23_TRANSFER_CARRY` | Change segment-B initial depth or duplicate the boundary | Carry/sequence invariant |
| `M24_TRANSFER_HISTORY` | Move Pump A exposure to Pump B at transfer | History ownership invariant |
| `M25_SECOND_TRANSFER` | Add another duty change | Transfer-limit invariant |
| `M26_AMBIGUITY_COLLAPSE` | Make both anchor histories share a latent state or response | Ambiguity requirement |
| `M27_LABEL_ASYMMETRY` | Change a label-neutral coefficient for Pump B | Label-symmetry rejection |
| `M28_DIAGNOSTIC` | Add an unapproved warning or hidden lifecycle error | Diagnostic rejection |
| `M29_PROMOTABLE` | Mark W3 candidate as promotable or certified | Maturity-boundary rejection |
| `M30_FORBIDDEN_FIELD` | Add power, action, obligation, score, or closure data | Output/scope rejection |

Mutations whose rejection depends on magnitude remain red until W4 supplies
the relevant threshold. B5 may not choose an obviously large mutation and
claim the minimum meaningful detection boundary is settled.

## 22. W2 diagnostic-case certification map

| W2 case | Required W3 checks |
| --- | --- |
| `G00_ZERO_STATIC` | Exact settings/time/inflow; storage, zero-flow branch, volume, overflow, and non-promotion |
| `G10_CLEAN_A_BASE` | Base inflow reconstruction, automatic control, clocks, mass/volume, roots, full pipe |
| `G11_CLEAN_B_BASE` | All G10 checks plus exact label transformation |
| `G12_CLEAN_ASSESS` | Clean analytical root, head/system residuals, drawdown capability pass |
| `G20_OBSTRUCTION_HALF` | Primary curve reconstruction, valid root, capability relation to clean |
| `G21_OBSTRUCTION_TRIGGER` | Independent trigger classification and no improvement |
| `G22_OBSTRUCTION_UPPER` | Upper-state validity, monotonic degradation, trigger classification |
| `G30_CLEARANCE_HALF` | Secondary curve reconstruction, valid root, distinct mechanism |
| `G31_CLEARANCE_UPPER` | Upper-state validity and non-improvement |
| `G40_COMBINED_HALF` | Combined equation, no cross-reset, consequence ordering |
| `G41_COMBINED_UPPER` | Limiting/no-drawdown consequence and possible level rise |
| `G50_CLEAR_A_PRE` | History A analytical state and visible flow |
| `G51_CLEAR_A_POST` | Exact clearing transition, history retention, post-clear response |
| `G52_CLEAR_B_PRE` | History B analytical state and visible flow equality to G50 |
| `G53_CLEAR_B_POST` | Exact clearing transition and response separation from G51 |
| `G60_REPAIR_PRE` | Combined pre-repair state and resource metadata |
| `G61_REPAIR_POST` | Exact repair transition, history retention, post-repair response |
| `G70_TRANSFER` | Segment identities, carry, sequence, settings, clocks, histories, continuity |
| `G80_NO_MAINTENANCE` | Exact progression at all checkpoints, clipping, clock distinction, non-improvement |

Every applicable structural and numerical check runs for every case. This
table names the additional relational purpose; it is not permission to skip
mass balance or representation checks in a mechanism case.

## 23. Diagnostic treatment

Normalized generator diagnostics are necessary evidence that the W2
generation attempt followed its declared engine lifecycle. They are not an
independent hydraulic oracle.

The certifier independently verifies:

- exact expected diagnostic keys;
- exact engine version, flow-unit code, report step, element names, counts, and
  order declared by W2;
- no engine lifecycle error;
- completion marker present;
- warnings empty or exactly allowed by a later explicit amendment;
- convergence-at-all-steps marker consistent with the reported non-converging
  percentage;
- finite signed continuity percentage; and
- diagnostic identity bound into the semantic candidate.

An error, missing completion marker, unknown warning, version mismatch,
element mismatch, or internal contradiction rejects exactly. The numerical
continuity percentage is only an observation until W4 preregisters its
treatment. A clean diagnostic record cannot override an independent residual
failure.

## 24. Certification result states

The certifier result uses one terminal state:

| State | Meaning |
| --- | --- |
| `certifier-input-reject` | Required byte role missing, duplicated, or unreadable |
| `structural-reject` | Bytes, schema, representation, unit, identity, or canonical form invalid |
| `exact-reject` | Exact W1/W2 rule, state transition, topology, sequence, or maturity invariant violated |
| `qualitative-reject` | Required monotonicity, ordering, symmetry, ambiguity, or non-worsening relation violated independent of tolerance |
| `quantitative-pending-w4` | All earlier checks pass, but at least one required residual lacks a preregistered W4 tolerance |
| `certifier-internal-error` | The certifier cannot complete its own calculation deterministically |

Precedence is the table order except that an internal error is always reported
as an internal error and never converted into candidate rejection.

There is intentionally no `pass`, `accepted`, `certified`, `promotable`, or
`V3` terminal state in the W3-only result vocabulary. After W4, the composed
protocol may add a quantitative pass state through an explicit versioned
amendment. W5 and B5 still own lineage and actual certification evidence.

The result records:

- protocol and authority identities;
- recomputed input identities;
- terminal state and first failing stage;
- exact checks attempted and outcomes;
- all residual definitions and observed values;
- no tolerance value unless bound to an accepted W4 identity;
- reference-case and mutation-case identities;
- certifier dependency/environment receipt identity;
- deterministic result-content identity; and
- explicit `promotable: false`.

This is a research result shape, not a production schema.

## 25. Stop, repair, and return rules

W3 stops and returns to W2 if:

- the permitted semantic bytes cannot support an independent mass, head,
  operating-point, control, or transfer check;
- certification requires raw SWMM artifacts or a report parser;
- case meaning cannot be reconstructed without generator objects;
- materialized curve evidence is not sufficient to prove what entered the
  engine; or
- an output/source mapping is ambiguous.

W3 stops and returns to W1 if:

- an equation, boundary condition, intervention, clock, observation, resource,
  or capability rule is under-specified for independent calculation;
- a required root is not uniquely bracketed inside the declared family;
- observation ambiguity depends on an unstated quantization rule; or
- mechanism or intervention isolation cannot be expressed without a new
  physical assumption.

W3 stops and returns to B3 if:

- independence requires reproducing undocumented SWMM internals;
- SWMM behavior is the only possible expected-value source; or
- the chosen engine role has expanded beyond candidate hydraulic generation.

W3 stops outright if:

- generator or SWMM code is imported into the certifier;
- one shared project helper owns a claim-critical calculation in both paths;
- expected values are generated from the candidate under test;
- a missing tolerance is replaced with an observed “close enough” value;
- a failing residual is hidden by a clean engine diagnostic;
- malformed or unknown data are ignored;
- a candidate is repaired in place;
- a path, filename, or workspace becomes identity;
- power or another excluded quantity becomes evidence without returning to W1;
  or
- a W3 result claims certification, promotion, operational validity, or
  real-world accuracy.

## 26. Implementation and TDD handoff to B5

Executable work begins only after all B4 packages are accepted. B5 must
implement this certifier test-first and in a package separate from the
generator.

The required implementation order is:

1. failing forbidden-dependency and environment-absence tests;
2. failing byte-role, canonical parsing, exact-key, unit, and identity tests;
3. failing binary32 decode and semantic-hash tests;
4. failing W1 parameter and dimensional tests;
5. failing independent pump/system/root reference tests;
6. failing curve reconstruction tests;
7. failing RK4, mass, volume, and overflow tests;
8. failing control, setting/flow, clock, and history tests;
9. failing intervention, transfer, resource, observation, and label tests;
10. every invalid mutation in section 21;
11. integration against real W2 semantic candidates with SWMM and generator
    physically absent from the certifier environment; and
12. an end-to-end generator-byte-bundle to certifier-result run across the
    complete W2 catalogue.

Unit, integration, and end-to-end tests are all required. There is no mock
SWMM path because the certifier does not call SWMM at all. Integration and
end-to-end tests use real W2-produced candidate bytes; a fabricated candidate
cannot establish generator/certifier boundary compatibility.

The implementation must also produce:

- a complete dependency inventory;
- an import graph;
- a forbidden-symbol and forbidden-package scan;
- an environment receipt proving generator/SWMM absence;
- deterministic rerun evidence; and
- negative evidence that invalid mutations are rejected.

No executable code belongs in this W3 planning slice.

## 27. Handoff to B4-W4

W4 must consume the exact residual and relation identities in section 13 and:

1. classify each as exact, absolute, relative, integral, temporal, or
   qualitative;
2. derive every numerical tolerance before any family run;
3. define binary32 representation floors separately from physical or numerical
   method discrepancy;
4. define pointwise and cumulative mass/volume treatments;
5. define candidate-versus-analytical head and root-flow treatments;
6. define candidate-versus-RK4 trajectory treatments;
7. define automatic-control edge alignment and off/on flow thresholds;
8. define full-pipe capacity treatment;
9. define engine continuity-diagnostic treatment without replacing independent
   balance;
10. define label-mirror comparison;
11. define capability-boundary margin;
12. define intervention-response and ambiguity-separation margins;
13. perturb pump-curve resolution, routing/report resolution, and bounded W1
    assumptions;
14. distinguish per-case rejection from family-level rejection; and
15. version the composed result state that can exist only after W4.

W4 may add sensitivity cases and thresholds. It may not weaken an exact
invariant, change an equation, import a shared helper, or tune a limit after
seeing generator output.

## 28. B4-W3 acceptance gate

| Requirement | W3 decision |
| --- | --- |
| Separately executable boundary defined | Pass |
| Inputs restricted to W2 content bytes | Pass |
| Raw solver and generator access prohibited | Pass |
| Every common dependency disclosed | Pass |
| Generator, SWMM wrapper, and solver libraries forbidden | Pass |
| Independent equations frozen | Pass |
| Independent root and trajectory methods frozen | Pass |
| SI units and dimensional checks frozen | Pass |
| Residual definitions frozen without selecting tolerances | Pass |
| Analytical and limiting reference cases defined | Pass |
| Invalid mutation catalogue defined | Pass |
| Mass balance and operating-point checks defined | Pass |
| Clock and history checks defined | Pass |
| Transfer and intervention checks defined | Pass |
| Observation ambiguity and quantizer defined | Pass |
| Label symmetry transformation defined | Pass |
| Certifier can reject without a generator assertion | Pass by protocol |
| W4 authority preserved | Pass: every numerical acceptance remains pending |
| No production or executable research surface created | Pass |
| B4 or V3 completed | No |

**W3 decision: accept `B4-D13` and open B4-W4 only.**

This decision says that B5 can implement a genuinely independent rejection
path without inventing the calculation boundary. It does not say that any
candidate has passed that path.
