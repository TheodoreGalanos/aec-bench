# ASW-4C execution and recovery findings

## Typed attrition

The 64 frozen trajectories completed with four host-fault records and no
replacement trajectories:

- one expired AWS credential before a model outcome;
- one initial 40,000-token adapter stop after measured use had passed the
  configured value;
- one concurrent station-tool mutation that selected a stale-view commit; and
- one denied `bedrock:CountTokens` request before model inference.

Three host faults occurred in the current-view arm and one occurred in the
structured-handover arm. The arm imbalance was two, which met the frozen
maximum.

The concurrent tool fault retained two provider calls, but the adapter version
in use at that point did not retain their token counts after the host exception.
The final input, output, and total token values therefore contain one explicit
measurement gap. The trajectory remains a typed host fault and was not
repeated.

## Runtime corrections

The station tools now serialize mutations inside one trajectory. This prevents
parallel calls from publishing two commits based on the same prior view.

The initial token amendment removed token use as a validity stop. The USD
authority remained hard. A conservative reserve later stopped the runner after
trajectory 49 because it assumed that all 16 calls in the next trajectory
would use the 500,000-token input ceiling.

The replacement spend guard derives a cumulative input allowance from the
remaining phase spend. It reserves:

- 16 maximum 2,048-token outputs; and
- one complete 500,000-input-token response for post-response limit
  detection.

It does not call the denied provider `CountTokens` operation. The approved
provider-call, USD 37, 16-turn, and 2,048-output-token controls did not change.

## World-owned terminal states

One trajectory created a transfer-required restriction after the one permitted
duty transfer had already been used. The host could not advance time. The
world was valid, the continuity failure was attributable to the agent action,
and the trajectory remained eligible.

Two completed trajectories passed the hidden evaluation time before the host
evaluation step. In each case, the durable world chain contained an exact state
at the frozen endpoint. Recovery selected the last valid state at that time,
evaluated an immutable temporary prefix, and retained the later world state
separately. Both trajectories remained eligible and were not repeated.

## Final execution totals

- Planned trajectories: 64.
- Durable completion records: 64.
- Provider requests: 380.
- Retained measured input tokens: 3,356,400.
- Retained measured output tokens: 169,046.
- Retained measured total tokens: 3,525,446.
- Token-measurement gaps: 1 host-fault response.
- Estimated spend: USD 13.865403.
- Host faults: 4.
- Endpoint-prefix recoveries: 2.
- Repeated or replacement trajectories: 0.

These values were independently reloaded from the immutable run root.
