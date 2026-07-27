# ABOUTME: Records the approved B5 repair to the W2-W4 SWMM mapping after real-engine falsification.
# ABOUTME: Replaces only the engine representation and dependent checks while preserving W1 physics and B5 boundaries.

# AU-NSW-LH-SYN-SPS-v1 — B5 engine-mapping repair

## 1. Decision

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B5 — World-family implementation` |
| Internal gate | `B5-W1 — Real generator` |
| Status | **Approved repair; implementation and certification still pending** |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Repair identity | `asw-0b5.engine-mapping-repair.v1` |
| Repaired generator protocol | `asw-0b5.generator-protocol.v3` |
| Repaired engine settings | `asw-0b5.swmm-settings.v2` |
| Generator protocol predecessor | `asw-0b4.generator-protocol.v2` |
| Machine authority | `asw-0b5-world-family/declarations/w2-w4-engine-mapping-repair.json` |

Theo approved this repair after the first real B5 execution falsified the
accepted W2 conduit mapping. The repair is narrow: it changes how the already
accepted W1 pump and system equations are represented inside SWMM and updates
the dependent W3/W4 checks. It does not change a W1 value, equation, bound,
case meaning, claim, intervention, clock, resource, actor-visible field,
institutional rule, package role, production boundary, or V-level.

The predecessor W2, W3, and W4 records remain historical authority except
where this repair explicitly supersedes them.

## 2. Falsifying evidence

The exact pinned B5 engine build passed its source, patch, Release,
one-thread, artifact, version, rights, and upstream-test gates.

The original W2 mapping was then exercised with real SWMM 5.2.4:

| Probe | Result |
| --- | --- |
| Original `G21` horizontal conduit | `WARNING 04`, `2.52%` nonconverging steps, `0.285%` continuity error |
| Original force-main parameter coverage | `system.K_minor` had no SWMM mapping |
| Conduit with explicit minor loss and steady initialization, `G21` | Zero warning, `0.00%` nonconverging, `0.000%` continuity |
| Same repaired conduit under automatic `G10` cycling | `6.31%` nonconverging, `-15.339%` continuity |

The failures are decisive:

- W2 permits no warning and requires exact zero nonconverging steps;
- W4 `C-R23` caps absolute engine continuity error at `0.05%`;
- omitting `system.K_minor` changes the W1 operating point; and
- a mapping that succeeds only for forced snapshots cannot represent the
  required automatic base cases.

Increasing iteration count, changing the surcharge method, and changing the
routing step did not make the original representation satisfy the accepted
gates. Those experiments remain disposable research evidence and do not
authorize tolerance tuning or a warning allowlist.

## 3. Selected repair

### 3.1 Net-head engine curve

W1 already owns the complete physical relation:

```text
H_pump(Q, o, c) = H_static(h) + H_loss(Q)
```

where:

```text
H_static(h) = z_d - h

H_loss(Q) =
    f(Q) (L/D) v(Q)^2/(2g)
    + K_minor v(Q)^2/(2g)
```

The repaired generator derives the engine-only relation:

```text
H_net(Q, o, c) =
    max(0, H_pump(Q, o, c) - H_loss(Q))
```

SWMM applies `H_net` between the wet well and a fixed stage `z_d`. Therefore
its operating point satisfies the original W1 pump/system equation without a
dynamic conduit surrogate.

The support flow is the unique internal root:

```text
H_pump(Q_support, o, c) = H_loss(Q_support)
```

The generator samples `H_net` with the same deterministic decimal,
quantization, endpoint, monotonicity, and `N=32` rules used by W2. It also
retains the original W1 pump-curve bytes separately. The net-head curve is an
engine representation, not a replacement physical pump curve, commercial
curve, or promoted runtime contract.

### 3.2 Fixed-HGL engine boundary

SWMM 5.2.4 permits only one inlet link at an outfall. The repaired input
therefore uses two engine outfall elements:

```text
O_HGL_A
O_HGL_B
```

Both have exact fixed stage `system.z_d`. Pump A connects only to `O_HGL_A`;
Pump B connects only to `O_HGL_B`. At most one pump can run under W1, so the
elements represent one physical discharge HGL through two engine endpoints.
They are not two physical outfalls, managed components, standby paths, or
actor-visible assets.

The exact engine elements are:

```text
nodes  = {WW_B4, O_HGL_A, O_HGL_B}
links  = {L_PA, L_PB}
curves = {C_EA, C_EB}
```

`J_DIS`, `L_FM`, `C_PA`, and `C_PB` cease to be engine elements. `C_PA` and
`C_PB` remain canonical original-curve evidence outside the `.inp`.

The exact input sections become:

```text
[TITLE]
[OPTIONS]
[OUTFALLS]
[STORAGE]
[INFLOWS]
[PUMPS]
[CURVES]
[TIMESERIES]
[REPORT]
```

No conduit, x-section, loss, outlet, junction, hydrology, control-rule,
coordinate, label, or free-form metadata section is permitted.

### 3.3 Exact terminal-duration compilation

Real lifecycle execution found a separate SWMM 5.2.4 representation issue.
The pinned source computes its internal integer-second duration as:

```text
TotalDuration =
    floor((EndDateTime - StartDateTime) * 86,400)
```

An integer `HH:MM:SS` end time compiled the accepted `120 s` and `3,600 s`
horizons to one period fewer. Adding a whole second was not a valid general
repair: it compiled `120 s` correctly but compiled `3,600 s` to one period
too many.

The repaired renderer therefore writes `END_TIME` as decimal hours:

```text
engine_end_time_hours = (semantic_horizon_s + 0.5 s) / 3,600
```

using 34-digit decimal arithmetic. The half-second is a version-specific
input-compilation guard. It makes the pinned engine's floored
`TotalDuration` equal the declared integer semantic horizon; it does not add
a report period, extend a physical case, or alter semantic time. Every run
must still return exactly `semantic_horizon_s` one-second periods. An extra
or missing period rejects.

The real W1 catalogue replay exercised all accepted horizons (`60 s`,
`120 s`, `3,600 s`, and `28,800 s`) twice with exact expected period counts.

## 4. Semantic-output repair

The repaired generator continues to extract:

- wet-well depth, head, volume, lateral inflow, and flooding;
- Pump A and Pump B flow;
- Pump A and Pump B exact solver settings; and
- the independent integer time grid.

It derives two series without introducing new physics:

```text
force_main_flow_m3_s =
    correctly_rounded_binary32(
        pump_a_flow_m3_s + pump_b_flow_m3_s
    )

discharge_head_m =
    correctly_rounded_binary32(system.z_d)
```

The first is valid only after exact no-simultaneous-pumping checks. The second
is the declared fixed-HGL boundary, not a measured engine conduit head.

`force_main_capacity_fraction` is removed. A non-existent engine conduit
cannot provide evidence of pipe fill.

Each candidate carries both original-pump-curve and net-head-engine-curve
bytes and identities. W3 independently reconstructs both. It does not trust
the generator's loss transformation.

## 5. W3 certification repair

W3 retains all physical equations, root, trajectory, mass balance, setting,
clock, intervention, transfer, observation, ambiguity, label, and mutation
checks.

The following dependent checks change:

- curve evidence now includes the original W1 curve and the net-head engine
  curve for each pump;
- W3 reconstructs `H_loss`, the support root, and every net-head point without
  generator helpers;
- candidate pump flow is compared with the original W1 pump/system root;
- force-main flow must equal the correctly rounded mutually exclusive pump
  sum;
- discharge head must equal the fixed `system.z_d` representation; and
- `C-R09` becomes an independent full-pipe-model applicability check using
  the declared diameter, flow interval, velocity, and Reynolds-number
  envelope rather than an engine capacity field.

The certifier still runs with generator code, SWMM, `.inp`, `.out`, `.rpt`,
and engine paths physically absent.

## 6. W4 sensitivity repair

W4 retains every parameter, OAT, interaction, boundary, observation,
progression, intervention, resource, replay, tolerance, and qualitative
ordering gate.

Engine variants change only where they depended on the removed conduit:

| Variant | Repaired meaning |
| --- | --- |
| `ENG.00.base` | Net-head curve `N=32`, one-second reference grid |
| `ENG.01.curve-16` | Net-head curve `N=16` |
| `ENG.02.curve-64` | Net-head curve `N=64` |
| `ENG.03.report-2s` | Routing/rule/wet/dry `1 s`, report `2 s` |
| `ENG.04.route-report-2s` | Routing/rule/report/wet/dry `2 s` |
| `ENG.05.outfall-order-swap` | Reverse the two equal-stage outfall declaration rows |
| `ENG.06.outfall-target-swap` | Swap the equal-stage Pump A/Pump B engine targets while preserving physical labels |

`ENG.05.sentinel-low` and `ENG.06.sentinel-high` are superseded because no
Manning sentinel or conduit remains.

The repaired outfall variants must preserve semantic values, physical labels,
case classifications, and replay identities after name-based extraction.
Index-based extraction fails.

## 7. Real-engine repair probe

Before this decision was approved, the proposed mapping was exercised as a
disposable real-engine probe:

| Evidence | Result |
| --- | --- |
| W2 case IDs | All 19 |
| Engine executions per workspace | 23: 17 single cases, two G70 segments, four G80 checkpoints |
| Fresh workspaces | Two |
| Engine warnings/errors | Zero |
| Nonconverging steps | `0.00%` for all 46 executions |
| Continuity error | `0.000%` for all 46 executions |
| Relative output inventory | Exact match |
| Raw binary output hashes | Exact match for all 23 corresponding executions |

This probe selects the repair direction. It is not the B5-W1 generator,
semantic extraction, setting trace, independent certification, W4 result,
promotion package, V3 decision, or retained final evidence. B5 must reproduce
the result through committed test-first code.

## 8. Boundaries and invariants

The repair does not authorize:

- a fallback or mock solver;
- generator self-certification;
- hiding an engine warning or nonconverging step;
- dropping `L`, `D`, `epsilon`, `K_minor`, `rho`, `mu`, or `g`;
- treating the net-head curve as a real pump curve;
- simultaneous pumping;
- a second physical discharge path;
- promotion of engine input, output, report, build, or curve-layout bytes;
- production imports from `research/`;
- changes under `src/aec_bench`; or
- study, action, authority, obligation, handover, scoring, or runtime meaning.

If the committed implementation cannot reproduce the complete real-engine
probe, preserve original-curve evidence, support independent certification,
or satisfy W4 without fitted tolerance, B5 stops. It does not return to the
rejected conduit representation.
