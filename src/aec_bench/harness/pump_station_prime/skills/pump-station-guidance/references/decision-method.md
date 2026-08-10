# Pump-station decision method

Use this method for each decision. It does not define an action sequence.

## 1. Protect service

Check the required service over the full proposed work duration. Identify which pumps can run now and which pumps are assured for outage planning. These are different conditions.

Do not make an operating or maintenance change that creates an avoidable service deficit.

## 2. Check work feasibility

For the highest-priority actor-addressable work, check:

- the action input schema;
- the bound backlog and evidence identifiers;
- active or conflicting processes;
- required resource capacity;
- the complete remaining resource window;
- outage capacity during the work;
- the newest decision ID.

## 3. Predict, act, and compare

Record the expected observable change. Make one action. Compare the returned next observation with the prediction before choosing another action.

An applied result advances the causal state. A rejected result normally leaves the state unchanged and supplies a reason. A failed call can indicate an action argument, decision, or transport problem. Keep these outcomes separate in the ledger.

## 4. Use rejection codes

- A process conflict means another process owns the required work lane or dependency.
- A resource-window rejection means the work cannot fit the current declared window.
- An outage-capacity rejection means the proposed work would leave insufficient permitted service.
- A backlog or evidence binding rejection means the request does not match the current actor-visible record.
- A stale decision requires a new observation.
- An action-argument error requires correction against the action schema.

Do not repeat a rejected request until a relevant state fact, decision ID, argument, or evidence binding changes.

After a `planned-outage-capacity` rejection, do not repeat the same inspection until the current actor-visible state
shows new non-target assurance through the full work duration or other relevant world evidence. A non-target pump that
is only run eligible does not provide assurance for outage planning.

## 5. Limit documentary search

Search only for content needed by the current decision. After `NO_ACCESSIBLE_RESULT`, stop the equivalent search. Search again only when the query scope or available information changes.

## 6. Stop at the authority boundary

Complete supported actor work while service and evidence remain valid. When further progress depends on a host-owned decision, record that dependency and stop. Do not claim the world is complete only because the Prime turn ends.
