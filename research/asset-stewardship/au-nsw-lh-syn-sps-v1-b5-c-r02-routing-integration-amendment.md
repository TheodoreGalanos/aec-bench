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

For a report interval of duration `dt`, define independently reconstructed net
flow:

```text
Q_net,k =
    Q_in,k
    - Q_pumped,k
    - Q_overflow,k
```

The signed difference between SWMM's trapezoidal increment and the existing
right-end increment is:

```text
E_route,k =
    0.5 * dt * (Q_net,k-1 - Q_net,k)
```

At the start of every fresh SWMM segment:

```text
Q_net,0 = 0
```

Later values must come from the existing independent W1 inflow, pump, control,
settling, and overflow reconstruction. Candidate numerical depth, flow,
volume, continuity, or residual values cannot determine `E_route`.

The existing raw residual remains unchanged. The corrected comparison becomes:

```text
E_total,k = E_quad,k + E_route,k

r_corrected,k =
    r_raw,k - E_total,k
```

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
- reading candidate numerical values to fit the correction;
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
