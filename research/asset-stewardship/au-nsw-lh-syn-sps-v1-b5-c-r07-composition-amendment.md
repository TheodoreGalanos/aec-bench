# ABOUTME: Records the approved post-rejection amendment to the W4 C-R07 tolerance composition.
# ABOUTME: Preserves the original closure residual while adding its omitted curve and render bounds.

# AU-NSW-LH-SYN-SPS-v1 — B5 C-R07 composition amendment

## 1. Decision

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B5 — World-family implementation` |
| Amendment point | After the first V3 refusal and C-R08 amendment; before any successor generation |
| Status | **Approved pre-successor-run amendment** |
| Approval | Theo, `2026-07-28` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Amendment identity | `asw-0b5.w4-c-r07-composition-amendment.v1` |
| W4 predecessor hash | `56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f` |
| Quantitative-composition repair hash | `38ca15bf46f67ee98aa66539701bbd8fc1889c1e268d42f0f724f7942b3c2ff8` |
| C-R08 amendment hash | `047576621781aa294b8251be433b9dba7c2efd66ffe759e633d67f26960d9a65` |
| Machine authority | `asw-0b5-world-family/declarations/w4-c-r07-composition-amendment.json` |

This amendment adds the curve-chord and curve-head-render terms already owned
by `C-R06` to the sign-mirrored `C-R07` closure. It changes neither residual
equation nor any constant.

The amendment is issued before a successor generation exists. It does not
edit the first V3 refusal, relabel a failed result, or authorize promotion.

## 2. Candidate-independent finding

The approved quantitative-composition repair defines:

```text
C-R06 =
    H_pump(Q_candidate,o,c)
    - (
        H_static_semantic
        + H_loss(Q_candidate)
      )

C-R07 =
    H_static_semantic
    - (
        H_pump(Q_candidate,o,c)
        - H_loss(Q_candidate)
      )
```

Therefore, at the same sample:

```text
C-R07 = -C-R06
```

Both closures compare the same analytical W1 pump/system relation with a
candidate flow produced by the rendered 32-segment engine curve. The
predecessor `C-R06` budget includes:

```text
B_curve_H(32,o,c)
B_render_head
```

The predecessor `C-R07` budget omits both terms. That omission makes identical
curve discretisation admissible for one algebraic orientation and
inadmissible for its exact sign mirror.

The missing error class follows from the paired equations and the existing
curve representation. It does not depend on the candidate residual's
magnitude. The retained sample exposed the omission; it did not determine a
new coefficient, segment count, or ceiling.

## 3. Successor C-R07 rule

For every `steady-eligible` sample, retain the existing residual unchanged and
calculate:

```text
T07 =
    outward_sum(
        B32(H_discharge),
        B32(H_wet-well),
        B_curve_H(32,o,c),
        B_render_head,
        B_system_render,
        B64(H_system)
    )
```

Then require:

```text
T07 <= C_head_relative
abs(C-R07_raw_residual) <= T07
```

where:

```text
C_head_relative = 0.001 abs(H_reference)
```

The hard ceiling remains separate and is never substituted for `T07`.
Failure of the derived budget ceiling precedes residual comparison.

The existing definitions remain unchanged:

```text
B_curve_H(32,o,c) = H_0 A / (4 * 32^2)
B_render_head = exact half-quantum bound from the rendered curve-head bytes
```

The system-render interval and binary representation terms remain mandatory.
The curve and render terms cannot be pooled with, replaced by, or inferred
from `B_system_render`.

## 4. Preserved meanings

The amendment preserves:

- the raw C-R07 residual and its sign;
- the repaired C-R07 net-head/static-HGL equation;
- the fixed-HGL semantic role;
- `N=32` for the base candidate;
- the existing analytical `B_curve_H` formula;
- exact curve-head rendering and its existing quantum;
- every binary32, system-render, and binary64 term;
- steady-eligibility and turbulent full-pipe conditions;
- the existing `0.1%` head-relative hard ceiling;
- outward arithmetic and reject-before-residual precedence; and
- all W1, W2, W3, family, engine, and semantic candidate bytes.

`C-R06` does not change. The amendment restores consistent error ownership
between the paired closures without merging their residual identities.

## 5. Superseded text

Only W4 section 10.3's `T07` formula is superseded. The predecessor formula:

```text
T07 =
    B32(H_discharge)
    + B32(H_wet-well)
    + B_system_render
    + B64(H_system)
```

is replaced by the successor rule in section 3 above.

Every other C-R07 condition, every other residual rule, and the general W4
hard-ceiling rules remain authority unless separately amended.

## 6. Generation and evidence boundary

The successor execution must:

1. bind the exact C-R07 and C-R08 amendment declaration bytes into one new
   generation identity;
2. preserve V1 generation-declaration reload;
3. retain the first V3 refusal and its results unchanged;
4. record the C-R07 raw residual, each curve/render/system/representation
   term, the outward total, and hard ceiling separately;
5. reject a missing, negative, non-finite, inward, or candidate-fitted term;
6. continue to C-R08 only after C-R07 passes;
7. execute the complete affected W3-W5 path in a fresh absent output root;
8. create no package root unless the complete family passes; and
9. issue a new immutable positive or negative V3 decision.

## 7. Forbidden interpretations

This amendment does not authorize:

- changing the C-R07 residual equation or sign;
- changing `N`, `H_0`, mechanism state, or the curve-bound coefficient;
- using the observed residual as a curve bound;
- replacing `B_system_render` with the curve term or vice versa;
- using the hard ceiling as the tolerance;
- editing, deleting, or approving the failed V1 generation;
- skipping a later W4 family or W5 gate;
- importing research authority into production; or
- claiming V3, V4, empirical calibration, or operational fitness.

The canonical JSON declaration is executable research authority. This
Markdown record explains Theo's decision and is not parsed at runtime.
