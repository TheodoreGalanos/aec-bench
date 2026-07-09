# Level-Crossing Issue Review Workflow

Work as an independent reviewing engineer. Use `/workspace/sources/` as the only numeric and documentary truth, and write the complete review to `/workspace/output.md`.

Use 8-12 turns:

1. Inventory every source document, revision, and status.
2. Build the crossing, route, sighting, controls, backup-power, communications, and degraded-mode identity ledger.
3. Trace the source-owned assessment bases and criteria.
4. Recompute only the evidence needed by the review matrix.
5. Check source identity, revisions, scenario continuity, missing evidence, and comment closure.
6. Assign one controlled status to every RLR item.
7. Link each failure, information request, and carried action to one exact RLR item.
8. Reconcile the readiness decision and claim boundary before writing the final structured block.

Do not invent missing values. Omit any `computed_evidence` key that cannot be recomputed and raise an information request for the missing field and source instead. Do not rename `computed_evidence` keys. Use exactly these keys when their source inputs are available:

- `maximum_train_speed_m_s`
- `provided_warning_time_s`
- `strike_in_distance_m`
- `warning_time_margin_s`
- `gate_horizontal_margin_s`
- `design_signal_load_w`
- `required_battery_capacity_ah`
- `installed_battery_capacity_ah`
- `battery_runtime_h`
- `battery_runtime_margin_h`
- `dc_voltage_drop_margin_percent`
- `fiber_link_margin_db`

End `/workspace/output.md` with exactly one fenced JSON block matching the instruction schema.
