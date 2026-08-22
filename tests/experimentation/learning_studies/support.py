# ABOUTME: Supplies deterministic adapter-boundary support for Learning Study integration tests.
# ABOUTME: Drives real artifact tasks and verifiers without a paid or hosted model call.

import json
from pathlib import Path

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus


class HeatLoadStudyAdapter:
    def __init__(self, workspace: Path, observations: list[dict[str, object]]) -> None:
        self.workspace = workspace
        self._observations = observations

    def execute(self, request: AdapterRequest) -> AdapterResult:
        instruction = (self.workspace / "instruction.md").read_text(encoding="utf-8")
        location = "brisbane" if "Brisbane" in instruction else "sydney"
        memory = self.workspace / ".aec-bench-learning" / "memory" / "method.json"
        feedback_root = self.workspace / ".aec-bench-learning" / "feedback"
        has_memory = memory.is_file()
        self._observations.append(
            {
                "location": location,
                "has_memory": has_memory,
                "has_feedback": feedback_root.is_dir() and any(feedback_root.iterdir()),
                "has_verifier": (self.workspace / "tests").exists(),
                "has_family_file": any(self.workspace.rglob("heat-load-single-room.toml")),
            }
        )
        content = (
            correct_heat_load_output(location) if location == "brisbane" or has_memory else incorrect_heat_load_output()
        )
        output = self.workspace / "output.md"
        output.write_text(content, encoding="utf-8")
        return AdapterResult(
            adapter_name="direct",
            resolved_model="fixed-test-model",
            configuration_record={},
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=[],
            usage_model_calls=1,
            usage_input_tokens=20,
            usage_output_tokens=10,
        )

    def adapter_name(self) -> str:
        return "direct"

    def resolved_model(self) -> str:
        return "fixed-test-model"


def correct_heat_load_output(location: str) -> str:
    if location == "brisbane":
        values = _heat_load_values(
            floor_area=85,
            area_per_person=10.0,
            outside_air_per_person=10.0,
            outdoor_temperature=38.3,
            outdoor_enthalpy=71.2,
            lighting_density=10,
            small_power_density=15,
            conduction_factor=18,
        )
    elif location == "sydney":
        values = _heat_load_values(
            floor_area=120,
            area_per_person=2.0,
            outside_air_per_person=12.0,
            outdoor_temperature=35.8,
            outdoor_enthalpy=65.8,
            lighting_density=12,
            small_power_density=10,
            conduction_factor=15,
        )
    else:
        raise ValueError(f"unsupported test location: {location}")
    return f"Calculation result\n\n```json\n{json.dumps(values, sort_keys=True)}\n```\n"


def incorrect_heat_load_output() -> str:
    return "Calculation result\n\n```json\n{}\n```\n"


def _heat_load_values(
    *,
    floor_area: float,
    area_per_person: float,
    outside_air_per_person: float,
    outdoor_temperature: float,
    outdoor_enthalpy: float,
    lighting_density: float,
    small_power_density: float,
    conduction_factor: float,
) -> dict[str, float]:
    people = floor_area / area_per_person
    outside_air = people * outside_air_per_person
    people_sensible = people * 75.0
    people_latent = people * 55.0
    lighting = floor_area * lighting_density
    small_power = floor_area * small_power_density
    conduction = floor_area * conduction_factor
    ventilation_sensible = (outdoor_temperature - 24.0) * 1.21 * outside_air
    ventilation_latent = (outdoor_enthalpy - 48.2) * outside_air / 0.833
    total_sensible = people_sensible + lighting + small_power + conduction + ventilation_sensible
    total_latent = people_latent + ventilation_latent
    return {
        "num_people": people,
        "total_outside_air": outside_air,
        "people_sensible_w": people_sensible,
        "people_latent_w": people_latent,
        "lighting_w": lighting,
        "small_power_w": small_power,
        "conduction_w": conduction,
        "ventilation_sensible_w": ventilation_sensible,
        "ventilation_latent_w": ventilation_latent,
        "total_sensible_w": total_sensible,
        "total_latent_w": total_latent,
        "total_cooling_w": total_sensible + total_latent,
    }
