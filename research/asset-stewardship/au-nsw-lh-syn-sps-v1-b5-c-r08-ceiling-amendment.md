# ABOUTME: Records the approved post-rejection amendment to the W4 C-R08 ceiling composition.
# ABOUTME: Preserves the failed generation while separating dynamic-model and numerical allowances.

# AU-NSW-LH-SYN-SPS-v1 — B5 C-R08 ceiling-composition amendment

## 1. Decision

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B5 — World-family implementation` |
| Amendment point | After the first B5-W3 through B5-W5 generation; before any successor run |
| Status | **Approved post-rejection amendment; successor generation not yet executed** |
| Approval | Theo, `2026-07-28` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Amendment identity | `asw-0b5.w4-c-r08-ceiling-amendment.v1` |
| W4 predecessor hash | `56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f` |
| Failed generation ID | `255e5b5cce2b4361bf37857ffbb386ef233bca47e9051b8f25e1689077edff06` |
| Failed C-R08 result ID | `d9e2408c7af861a6c3ea0befea0a1b6528efcd899305962d07217f1080b5c099` |
| Machine authority | `asw-0b5-world-family/declarations/w4-c-r08-ceiling-amendment.json` |

This amendment selects the second option retained by the failed generation:
the W4 `0.1%` C-R08 hard ceiling governs the non-dynamic numerical allowance,
while the hydraulic dynamic-model allowance remains separately derived and
separately ceilinged under W4 section 6.7.

The amendment changes no measured or generated value. It does not approve the
failed generation, edit its result, or authorize promotion. It defines the
successor rule that a new generation must execute.

## 2. Candidate-independent finding

For every positive reference flow, the predecessor rules define:

```text
B_dynamic_Q = 0.001 abs(Q_star)
C_flow_relative = 0.001 abs(Q_star)
```

They then require:

```text
T08 =
    B32(Q_candidate)
    + B_root
    + B_curve_Q
    + B_system_Q
    + B_dynamic_Q
    + B64(Q_star)

T08 <= C_flow_relative
```

Because `B_dynamic_Q` equals `C_flow_relative`, any positive representation,
root, curve, system, or binary64 term makes the rule impossible. This is a
symbolic contradiction for the rule class; it does not depend on the
candidate residual or on the retained G12 numerical values.

The failed generation exposed the contradiction and remains the evidence that
the predecessor rule fails closed. Its residual was not used to choose a new
constant, enlarge a ceiling, or fit an allowance.

## 3. Preserved meanings

The amendment preserves:

- `r_hyd = 0.001`;
- the formula for `tau_hyd` and `t_settle`;
- the formula `B_dynamic_Q = r_hyd abs(Q_star)`;
- the existing relative ceiling
  `C_flow_relative = 0.001 abs(Q_star)`;
- the existing observation ceiling
  `C_flow_observation = 0.25 observation.flow_resolution`;
- every representation, root, curve, system-render, and binary64 term;
- the raw W3 C-R08 residual and its sign;
- steady-eligibility, full-pipe, settling, and exact-role conditions;
- outward arithmetic and reject-before-residual precedence; and
- every W1 member, W2 case, engine mapping, candidate byte, and family probe.

The hydraulic dynamic term represents the declared difference between the
quasi-steady independent reference and dynamic-wave routing. It is not an
unexplained numerical error. The remaining C-R08 terms bound representation
and numerical construction error. Keeping those two classes explicit makes
each independently falsifiable.

## 4. Successor C-R08 rule

At each steady-eligible post-settling sample, calculate:

```text
C08 =
    min(
        0.001 abs(Q_star),
        0.25 observation.flow_resolution
    )

B_dynamic_Q = 0.001 abs(Q_star)

T08_numerical =
    outward_sum(
        B32(Q_candidate),
        B_root,
        B_curve_Q(32,o,c),
        B_system_Q,
        B64(Q_star)
    )

T08_total =
    outward_sum(
        B_dynamic_Q,
        T08_numerical
    )
```

The checks execute in this order:

```text
B_dynamic_Q <= C08
T08_numerical <= C08
abs(C-R08_raw_residual) <= T08_total
```

The first failure owns the terminal state. Neither `C08` nor `T08_total` may
replace a derived component. A component that cannot be constructed outward
and finitely is an internal error, not a pass.

This permits at most one independently ceilinged dynamic-model allowance and
one independently ceilinged numerical allowance. It does not create an
additional observation allowance, infer a correction, subtract the candidate
residual, or permit the two classes to trade budget.

`C-R14` continues to inherit C-R08 after settling and therefore inherits this
amended composition. No other residual rule changes.

## 5. Superseded text

Only these predecessor statements are superseded for `C-R08`:

1. W4 section 6.8's application of `T_derived <= C_hard` to the complete
   C-R08 allowance including `B_dynamic_Q`; and
2. W4 section 10.4's requirement that complete `T08` be no larger than both
   the relative and observation ceilings.

The general W4 rule remains unchanged for every other residual. For C-R08,
the successor interpretation is:

```text
explained dynamic-model allowance has its own ceiling
non-dynamic numerical allowance has the existing C-R08 hard ceiling
raw residual is compared with their outward total
```

The predecessor protocol and the failed execution record remain immutable.
This amendment is a successor delta, not an edit in place.

## 6. Generation and evidence boundary

The successor execution must:

1. bind the exact amendment declaration bytes into a new generation identity;
2. retain the predecessor W4 protocol and failed generation identities;
3. preserve the failed result under `results/v3-refusal` unchanged;
4. execute C-R08 with separate dynamic, numerical, and total fields;
5. record each component ceiling and first failure independently;
6. run the complete affected W3-W5 path in a fresh absent output root;
7. continue through the family only if the amended anchor passes every
   ordered W4 check;
8. create no package root unless the complete family earns
   `family-w4-checks-pass`; and
9. issue a new immutable positive or negative V3 decision.

Existing W1 and W2 definitions remain authority, but an old result may not be
relabeled, edited, or promoted. Reuse of unchanged definitions does not waive
fresh execution, replay, receipt, and identity requirements.

## 7. Forbidden interpretations

This amendment does not authorize:

- changing `r_hyd`, either hard ceiling, or any numerical term;
- fitting a tolerance or correction to candidate output;
- pooling unused budget between dynamic and numerical classes;
- deleting a failed sample, case, member, variant, grid, or mutation;
- skipping sibling execution after an amended anchor pass;
- mutating or replacing the first V3 refusal;
- creating package bytes before the complete family passes;
- importing research code or declarations into production; or
- claiming empirical calibration, operational fitness, V4, or production
  readiness.

The canonical JSON declaration is executable research authority. This
Markdown record explains Theo's decision and is not parsed at runtime.
