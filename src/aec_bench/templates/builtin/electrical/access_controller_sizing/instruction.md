# ABOUTME: Prompt template for access controller and power supply sizing tasks.
# ABOUTME: Presents door count, controller capacity, device currents, supply capacity, and backup duration.

You are a senior electronic security engineer sizing access control controllers and power supplies.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Door count | {{ door_count }} | count |
| Doors per controller | {{ doors_per_controller }} | doors/controller |
| Reader current per door | {{ reader_current_ma_per_door }} | mA |
| Lock current per door | {{ lock_current_ma_per_door }} | mA |
| Request-to-exit current per door | {{ request_to_exit_current_ma_per_door }} | mA |
| Controller current | {{ controller_current_ma }} | mA each |
| Power supply capacity | {{ power_supply_capacity_a }} | A |
| Backup duration | {{ backup_duration_h }} | h |
| Battery derating factor | {{ battery_derating_factor }} | - |

## Constraints

- Controllers required equals the ceiling of door count divided by doors per controller.
- Door device load equals door count times the sum of reader, lock, and request-to-exit currents, converted to amps.
- Total system load equals door device load plus controller load.
- Power supplies required equals the ceiling of total system load divided by power supply capacity.
- Battery capacity equals total system load times backup duration divided by the battery derating factor.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "controllers_required": <numeric_value>,
  "door_device_load_a": <numeric_value>,
  "total_system_load_a": <numeric_value>,
  "power_supplies_required": <numeric_value>,
  "battery_capacity_ah": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
