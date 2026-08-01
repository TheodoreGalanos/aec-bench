# ASW-6A architecture

Version 3 extends the task-owned pump-station state, receipt, snapshot, policy,
and transition records. Version 1 and version 2 keep their original serializer
profiles, durable bytes, state identities, reload, and replay behavior.

The host schedules one allowlisted evidence treatment through a separate
control request. The request binds the run, episode, branch, state, commit,
sequence, treatment class, target source, activation point, treatment version,
and visibility policy. The schedule is a durable zero-clock transition on the
same commit chain. Exact retries recover the original result.

The actor cannot call the host treatment controls. The actor receives only the
current effect through the normal version 3 projection. That projection shows
observation, production, and availability time; age; quality; source; component
scope; baseline; operating regime; acceptance; contradiction; supersession;
and applicability. It does not show treatment identity, hidden values,
unaffected controls, or future activation.

The condition check reads only the governed sensor source. Physical inspection
remains a separate action and evidence class. Condition-check evidence cannot
satisfy the physical-inspection rule for obstruction clearance.

Direct Python, installed JSON, and local Harbor use the same version 3 state
machine and durable repository. Independent replay reloads both actor proposals
and host-control transitions from immutable records.
