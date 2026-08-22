# Pump-component memory update

Update the structured memory from only the released public episode.

Use one top-level `components` map with a separate entry for each demonstrated component. Record its method, inputs, outputs, units, applicability conditions, checks, failure modes, and how its result can become another method's input. Preserve an existing component entry when a later episode adds another one.

When the memory contains more than one component, add an `integration` section. Record only the known output-to-input interfaces, unit transformations, assumptions, and cross-checks between those components.

Do not name, infer, or describe a later probe task. Do not copy task-specific numeric values as reusable rules. Do not add verifier files, hidden task state, or unreleased evaluation evidence.
