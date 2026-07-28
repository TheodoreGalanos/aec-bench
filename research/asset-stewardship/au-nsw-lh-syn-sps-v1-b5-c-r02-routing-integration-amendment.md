# ABOUTME: Records the approved correction for SWMM's first-interval routing integration.
# ABOUTME: Preserves the raw mass residual while repairing its independent signed correction.

# AU-NSW-LH-SYN-SPS-v1 — B5 first-interval routing-integration amendment

## 1. Decision

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B5 — World-family implementation` |
| Amendment point | After the C-R02 successor refusal; before any later successor generation |
| Status | **Approved pre-successor-run amendment** |
| Approval | Theo, `2026-07-28` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Amendment identity | `asw-0b5.w4-c-r02-routing-integration-amendment.v1` |
| Pinned engine | EPA SWMM `5.2.4` |
| Pinned source commit | `7952ca837988b1c32f791812eccc9fd64547e093` |
| Machine authority | `asw-0b5-world-family/declarations/w4-c-r02-routing-integration-amendment.json` |

This amendment fixes an error in the independent W4 correction. It does not
change the pump world, SWMM output, raw mass residual, tolerance, or hard
ceiling.

In plain language, SWMM uses the average of the flow at the beginning and end
of each routing step. Our checker had treated the end flow as if it applied
for the whole first second.

## 2. Root cause

The pinned SWMM source establishes two relevant facts.

First, a node begins with zero previous lateral flow:

```text
Node[j].oldLatFlow = 0
Node[j].newLatFlow = 0
```

Second, dynamic-wave storage advances using the average of the previous and
current net flow:

```text
dQ = current inflow - current outflow
dV = 0.5 * (previous net inflow + dQ) * dt
```

These rules are in the pinned engine's `src/solver/node.c` and
`src/solver/dynwave.c`. They are engine-algorithm evidence, not candidate
output.

For the clean automatic case, the current inflow at the end of the first
second is `0.005 m³/s`, while the previous engine flow is zero. SWMM therefore
adds:

```text
0.5 * (0 + 0.005) * 1 = 0.0025 m³
```

The existing right-end calculation instead subtracts:

```text
0.005 * 1 = 0.005 m³
```

That creates an artificial residual of `-0.0025 m³`. It explains the retained
failure without changing any physical parameter or fitting any tolerance.

## 3. Corrected signed term

For each report interval, define the exact validated semantic net flow:

```text
Q_net,k =
    Q_in,candidate,k
    - Q_A,candidate,k
    - Q_B,candidate,k
    - Q_overflow,candidate,k
```

These values come from the canonical semantic series after the certifier has
proved their shape, units, source bindings, replay identity, pump sum, off-flow
rules, and control edges. They are not used to select a tolerance or fit a
correction.

The source-defined routing term applies to every report interval:

```text
E_route,k =
    0.5 * dt * (Q_net,k-1 - Q_net,k)
```

At the start of every fresh SWMM segment:

```text
Q_net,engine,0 = 0
```

The term is an exact evaluation of the pinned engine algorithm. It is not an
empirical correction.

The W3 raw residual uses depth-derived storage. SWMM also emits the storage
volume that it advances. After C-R01 proves the exact depth/volume identity,
retain the signed representation difference:

```text
E_storage,k =
    A_w (h_candidate,k - h_candidate,k-1)
    - (V_candidate,k - V_candidate,k-1)
```

This term converts the raw depth-derived storage increment to the validated
engine storage increment. It does not change either candidate series.

The existing raw residual remains unchanged. The corrected comparison becomes:

```text
E_total,k = E_route,k + E_storage,k

r_corrected,k =
    r_raw,k - E_total,k
```

The independently reconstructed W1 quadrature and RK4 traces remain separate
physical and numerical evidence. They do not enter this engine mass identity
as a second signed correction. Adding both terms counts ordinary
trapezoidal change twice.

For C-R03, the storage representation terms are dependency-aware. The
intermediate storage values cancel in the cumulative balance:

```text
B_storage,prefix,n =
    T01(V_candidate,0, h_candidate,0)
    + T01(V_candidate,n, h_candidate,n)
    + B64(V_candidate,n - V_candidate,0)

T03,n =
    B_storage,prefix,n
    + sum(B_flow,k + B_method,k for k=1...n)
```

`T01` is the existing C-R01 pointwise storage-identity bound. This keeps the
depth-to-volume representation uncertainty that C-R01 proves, but the checker
does not sum the same intermediate storage representation as two independent
errors at every interval. The cumulative hard ceiling remains unchanged.

The existing outward method allowance, unexplained-error budget, and hard
ceiling remain mandatory.

## 4. Focused retained-evidence check

For the retained first interval:

| Quantity | Value |
| --- | ---: |
| Raw residual | `-0.00250003580133102 m³` |
| Routing-integration correction | `-0.0025 m³` |
| Corrected residual | `-0.00000003580133102 m³` |
| Existing allowance | `0.00000045211021993 m³` |
| Existing hard ceiling | `0.00007547676350249 m³` |

The corrected residual fits the existing allowance. No threshold, allowance,
or ceiling changes.

This focused check resolves only the identified first-interval discrepancy. It
does not claim that all later mass checks, the family, or W5 promotion pass.

## 5. Preserved boundaries

The amendment preserves:

- the retained failed generation and all its evidence;
- the W3 right-end raw residual and cumulative residual;
- the exact engine output and semantic candidate bytes;
- the W1 inflow schedule and all asset parameters;
- the C-R01 storage identity;
- the existing signed quadrature correction;
- every representation and rendering term;
- the existing unexplained-error allowance and hard ceilings;
- reject-before-residual precedence;
- C-R12 control-edge proof before candidate edge labels are used; and
- the package, production-import, and promotion gates.

## 6. Forbidden interpretations

This amendment does not authorize:

- deleting or ignoring the first sample;
- changing the initial depth or inflow to make the result pass;
- using candidate numerical values to select or enlarge a tolerance;
- using any equation other than the pinned source-defined trapezoidal
  identity;
- widening the tolerance or substituting the hard ceiling;
- relabelling either retained refusal;
- claiming later mass checks or the family pass;
- constructing a package or manifest; or
- importing research code or authority into production.

## 7. Next execution boundary

A later successor generation may bind this exact amendment and run the
affected W4/W5 path. That execution must stop at its first genuine later
failure or record a complete pass. Until then, the two retained W5 refusals
remain the only executed decisions.
