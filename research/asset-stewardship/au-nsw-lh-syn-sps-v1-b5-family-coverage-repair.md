# ABOUTME: Records the pre-generation W4 interaction repair required by independent W1 precondition execution.
# ABOUTME: Preserves both failed interaction members while restoring the preregistered minimum family coverage.

# AU-NSW-LH-SYN-SPS-v1 — B5 family-coverage repair

## 1. Decision

| Field | Value |
| --- | --- |
| Programme stage | `ASW-0B5 — World-family implementation` |
| Repair point | `B5-W3`, before any interaction member enters SWMM |
| Status | **Applied pre-generation repair; subject to review in this W3-W5 PR** |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Repair identity | `asw-0b5.w4-family-coverage-repair.v1` |
| W4 authority hash | `56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f` |
| Failed catalogue hash | `a210cda08dd68ac0106aee98d242f9fde0ce3fc74dcb4004e11cc00df8fe1425` |
| Machine authority | `asw-0b5-world-family/declarations/w4-family-coverage-repair.json` |

The first independent construction of the exact W4 interaction selections
found that neither non-anchor hydraulic interaction satisfied W1 membership.
W4 requires at least one valid non-anchor hydraulic interaction, so continuing
with the failed catalogue would make `family-w4-checks-pass` impossible.

This repair occurs before either failed member is rendered or executed by
SWMM. It uses only the accepted W1 equations and cross-constraints. No
candidate series, residual, engine diagnostic, tolerance, or desired V3
outcome was consulted.

## 2. Preserved failed members

| Probe | Exact first failure |
| --- | --- |
| `INT.01.hydraulic-supporting` | `bounded degraded state remains capable` |
| `INT.02.hydraulic-opposing` | `clean drawdown exceeds capability limit` |

The failures are retained as predecessor-catalogue evidence. They are not
relabeled as passing members and are not overwritten in place.

`INT.03.primary-dominant` also produces the expected precondition rejection
`ambiguity witness leaves bounds`. It is unchanged. W4 permits invalid
interaction members to remain boundary evidence, and
`INT.04.secondary-dominant` supplies the required valid non-anchor mechanism
coverage.

## 3. Selected repair

### 3.1 `INT.01.hydraulic-supporting`

Return only:

```text
pump.H_0 = anchor
pump.Q_0 = anchor
```

The repaired interaction retains its supporting wet-well diameter, level,
inflow, static-head, length, pipe-diameter, roughness, and minor-loss bound
selections. Removing the stacked upper pump makes the bounded fully degraded
state cross the W1 capability predicate while preserving the intended strong
hydraulic-system stress.

### 3.2 `INT.02.hydraulic-opposing`

Return only the system-curve group to anchor:

```text
system.z_d      = anchor
system.L        = anchor
system.D        = anchor
system.epsilon  = anchor
system.K_minor  = anchor
```

The repaired interaction retains its opposing wet-well diameter, level,
inflow, and pump bound selections. Removing the second stacked adverse group
restores clean capability while preserving a deliberately weak-pump,
high-inflow, high-storage hydraulic interaction.

## 4. Selection discipline

The repair uses semantic selection groups, not a numerical search for the
nearest pass:

- Pump design parameters are the owning group removed from the supporting
  interaction.
- System-curve parameters are the owning group removed from the opposing
  interaction.
- Every retained value remains exactly W1 lower, anchor, or upper.
- No new midpoint, coefficient, member, case, or tolerance is introduced.
- The fixed case maps and replay policy do not change.

The repaired members rerun the complete independent W1 precondition check.
They do not receive a relaxed predicate.

## 5. Boundaries

This repair does not authorize:

- changing W1 bounds, equations, cases, capability meaning, or family minimum;
- deleting either failed predecessor member;
- substituting a generated member after observing engine output;
- dropping an OAT, BND, ENG, grid, mutation, case, or replay;
- changing a W4 tolerance or qualitative ordering;
- treating an invalid interaction as accepted coverage; or
- claiming family acceptance, V3, promotion, or production authority.

The canonical JSON declaration is executable authority. This Markdown record
is decision evidence and is not parsed at runtime.
