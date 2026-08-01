# ASW-5 approved rule freeze

## Reference scenario

- Pump A has post-maintenance verification work.
- Pump B has inspection and obstruction-clearance work.
- Access preparation and repair-kit delivery are timed processes.
- The jobs share one access window, one repair kit, and one intervention slot.
- Access can be withdrawn during active work.
- A fresh agent must safely resume, cancel, or reorder work after handover.

## Process rules

- Dependencies are fixed AND lists.
- Valid states are `blocked`, `active`, `suspended`, `completed`, `failed`,
  `interrupted`, and `cancelled`.
- Access withdrawal automatically suspends access-dependent work.
- Suspension does not pause required follow-up due dates.
- Resume checks dependencies and resources again. It uses remaining duration.
- Resume does not repeat completed work.
- Cancellation releases unused resources. It does not remove operating limits
  or required follow-ups.
- A completion event cannot affect cancelled or completed work.

## Resource rules

- Access, the repair kit, and the intervention slot use explicit reservations.
- A resource cannot have two reservations at the same time.
- Access and intervention slots are released on suspension, cancellation, and
  completion.
- The repair kit stays assigned during suspension.
- The repair kit is consumed only after successful obstruction clearance.
- Cancellation releases an unused repair kit.
- Interrupted or suspended work has no partial physical effect.

## Dependency waiver

- Physical, safety, evidence, and resource dependencies cannot be waived.
- Only an administrative closeout dependency can be waived.
- Work Management is the approving role.
- The proposal must name accepted evidence.
- A waiver cannot complete work, satisfy a follow-up, create a resource, or
  remove an operating limit.

## Nested operating limits

- Access withdrawal creates a child `no_intervention` limit under the existing
  affected-pump limit.
- The child limit blocks resume until access returns.
- The parent limit stays active until its existing evidence rule is met.
- Agent views and handovers show the parent-child chain.

## Scope and authority

Theo approved these exact ASW-5 values on 2026-08-01. The stage is asset-local
and provider-free. ASW-6 through ASW-10, shared extraction, and a model study
remain outside this authority.
