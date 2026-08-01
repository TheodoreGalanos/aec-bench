# Source index

- `src/aec_bench/contracts/world_interface.py`: shared actor and control models.
- `src/aec_bench/harness/world_interface.py`: provider-independent actor validation.
- `src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/actor_interface.py`: task-owned action schemas and proposal conversion.
- `src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/world_control.py`: host-only pump-station controls.
- `src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/local_interface.py`: installed JSON request contract.
- `src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/world_session.py`: live actor implementation and existing tool wrappers.
- `src/aec_bench/cli/commands/pump_station_world.py`: installed transport.
