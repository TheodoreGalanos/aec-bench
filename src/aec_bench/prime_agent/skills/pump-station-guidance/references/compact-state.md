# Compact state and action ledger

Keep rich results in the kernel and expose only the fields required for the next decision.

## State shape

Use one mapping with these concepts:

```python
compact_state = {
    "time": None,
    "decision_id": None,
    "required_service": None,
    "running_pumps": [],
    "assurance": {},
    "active_process": None,
    "resource_window": None,
    "restrictions": [],
    "priority_work": [],
}
```

Update it from the latest observation. Print a small projection, not the source object.

```python
print({
    "time": compact_state["time"],
    "required_service": compact_state["required_service"],
    "active_process": compact_state["active_process"],
    "priority_work": compact_state["priority_work"],
})
```

## Ledger shape

Append one entry for every `invoke` attempt:

```python
action_ledger.append({
    "request_id": request_id,
    "decision_id": decision_id,
    "action": action_name,
    "expected_result": expected_result,
    "status": result_status,
    "reason_code": reason_code,
    "next_decision_id": next_decision_id,
})
```

Include rejected and failed attempts. Use this ledger for the final action count and outcome account.

## One-cell action pattern

Use this schematic shape after setup. Replace the placeholders with the action, arguments, state fields, and output fields
justified by the current actor-visible evidence. It is not a task solution or a fixed action sequence.

```python
expected_result = ...
result = await aec_world.invoke(action_name, arguments, decision_id=decision_id)
action_ledger.append({
    "action": action_name,
    "expected_result": expected_result,
    "status": result["status"],
    "next_decision_id": result["next_observation"]["decision_id"],
})
compact_state.update({
    "decision_id": result["next_observation"]["decision_id"],
    # Add only state fields needed for the next decision.
})
print({
    "status": result["status"],
    # Add only changed fields needed for the next decision.
})
```

Handle an actor error in the same action cell when practical and record its code in the ledger. Do not fabricate a next
observation when the actor did not return one.

## Output discipline

- Assign the full result to a variable.
- Select the current fields in Python.
- Print one small mapping or short table.
- Do not use an indented JSON dump for a complete capability, observation, or action result.
- Do not repeat a printed field when its value did not change.
