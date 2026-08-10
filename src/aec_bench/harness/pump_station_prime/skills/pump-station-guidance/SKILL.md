---
name: pump-station-guidance
description: Use compact state, exact action accounting, and pump-station stewardship checks in an AECBench world.
metadata:
  status: experimental
  validation: two-reference-profiles
---

# Pump-station guidance

guidance_id: aecbench.pump-station-guidance

This skill is experimental. It has qualification evidence from two registered reference profiles. It does not supply a
solution plan.

The task objective and actor authority remain in the initial prompt and the `aec-world` skill. Use only the available actor operations.

## Keep compact computational state

- Keep full observations and action results in Python variables. Do not print the full objects.
- Print only the named fields required for the next decision.
- Keep one compact state with current time, newest decision ID, service need, running pumps, assurance, active process, resource window, restrictions, and highest-priority work.
- Update the compact state after every action result.
- Use the next observation in an action result. Do not call `observe()` again when that observation is current.
- Record every `invoke` in an exact ledger. Include applied, rejected, and failed calls.
- Build the final action account from the ledger. Do not reconstruct it from memory.

See [compact-state.md](references/compact-state.md) for a generic notebook pattern.

## Use one notebook cell per action attempt

After initial setup, normally use one IPython cell for each `invoke` attempt. In that cell:

1. Record the expected actor-visible result.
2. Invoke the selected action.
3. Append the actual applied, rejected, or failed outcome to the ledger.
4. Update compact state from the returned next observation when one is available.
5. Print only the small projection needed for the next decision.

Do not use separate model turns only to append the ledger, update compact state, or reprint an unchanged result. This is
a working method, not an action-selection rule. You must still choose the action and arguments from current actor-visible
evidence.

## Make one evidence-based decision at a time

- Inspect an action input schema before the first use of that action.
- Before an intervention, record the expected observable result.
- After the intervention, compare the next observation with that expectation.
- Treat a rejection as evidence about the current causal state.
- Do not repeat the same request while its decision state and relevant facts are unchanged.
- Distinguish process conflict, resource window, outage capacity, backlog binding, evidence binding, stale decision, and action-argument errors.
- Check required service through the full duration of field work.
- Distinguish run eligibility from assurance for outage planning.
- Qualified `/refine` lesson: after a `planned-outage-capacity` rejection, do not repeat the same inspection until the
  current actor-visible state shows new non-target assurance or other relevant world evidence. Run eligibility alone is
  not assurance for outage planning.
- Search documentary evidence only when the current decision needs documentary content.
- After `NO_ACCESSIBLE_RESULT`, do not make an equivalent search unless the information set or query scope changes.
- Identify work that depends on a host-owned decision. Do not seek another control path.
- When supported actor progress ends, inspect the actor-visible final state and write the final report from the ledger.
  If the world remains live, report it as incomplete.

See [decision-method.md](references/decision-method.md) for the decision checks.

## Stay within scope

Do not infer hidden state, verifier expectations, rewards, host controls, or world files. Do not modify the supplied skills or harness. Do not use this guidance as evidence that the world is complete.
