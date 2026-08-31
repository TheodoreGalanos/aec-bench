# ABOUTME: Supplies deterministic adapter-boundary support for Learning Study integration tests.
# ABOUTME: Drives real artifact tasks and verifiers without a paid or hosted model call.

import json
import re
from pathlib import Path

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.tasks.loader import resolve_task_instance_dir


def resolve_learning_task_dir(tasks_root: Path, task_id: str) -> Path:
    """Resolve a learning-study task key to its source-controlled instance directory."""
    return resolve_task_instance_dir(task_id, tasks_root)


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
                "has_family_file": any(self.workspace.rglob("family.toml")),
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


class DrainageBoundaryStudyAdapter:
    def __init__(
        self,
        workspace: Path,
        *,
        acquisition_output: str,
        probe_output: str,
        observations: list[dict[str, object]],
    ) -> None:
        self.workspace = workspace
        self._acquisition_output = acquisition_output
        self._probe_output = probe_output
        self._observations = observations

    def execute(self, request: AdapterRequest) -> AdapterResult:
        manifest = (self.workspace / "sources" / "model-input-manifest.md").read_text(encoding="utf-8")
        is_acquisition = "| Catchment basis revision | Rev C |" in manifest
        namespace = self.workspace / ".aec-bench-learning"
        history_root = namespace / "history"
        memory_root = namespace / "memory"
        feedback_root = namespace / "feedback"
        has_history = history_root.is_dir() and any(path.is_file() for path in history_root.rglob("*"))
        has_memory = memory_root.is_dir() and any(path.is_file() for path in memory_root.rglob("*"))
        has_feedback = feedback_root.is_dir() and any(path.is_file() for path in feedback_root.rglob("*"))
        self._observations.append(
            {
                "task": "acquisition" if is_acquisition else "probe",
                "has_history": has_history,
                "has_memory": has_memory,
                "has_feedback": has_feedback,
                "has_verifier": (self.workspace / "tests").exists(),
            }
        )
        if is_acquisition:
            content = self._acquisition_output
        elif has_history:
            content = upstream_invalidation_output(self._probe_output)
        else:
            content = self._probe_output
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
            usage_input_tokens=40,
            usage_output_tokens=20,
        )

    def adapter_name(self) -> str:
        return "direct"

    def resolved_model(self) -> str:
        return "fixed-test-model"


class RetentionInterferenceStudyAdapter:
    def __init__(
        self,
        workspace: Path,
        *,
        neutral_output: str,
        observations: list[dict[str, object]],
    ) -> None:
        self.workspace = workspace
        self._neutral_output = neutral_output
        self._observations = observations

    def execute(self, request: AdapterRequest) -> AdapterResult:
        namespace = self.workspace / ".aec-bench-learning"
        memory_root = namespace / "memory"
        feedback_root = namespace / "feedback"
        has_memory = memory_root.is_dir() and any(path.is_file() for path in memory_root.rglob("*"))
        feedback_files = (
            tuple(path for path in feedback_root.rglob("*") if path.is_file()) if feedback_root.is_dir() else ()
        )
        has_interference_episode = any(
            "cairns-server-60m2" in path.read_text(encoding="utf-8") for path in feedback_files
        )

        if (self.workspace / "sources" / "model-input-manifest.md").is_file():
            task = "neutral-drainage"
            content = self._neutral_output
        else:
            instruction = (self.workspace / "instruction.md").read_text(encoding="utf-8")
            location = next(
                name for name in ("brisbane", "sydney", "adelaide", "cairns") if name.title() in instruction
            )
            task = location
            if location in {"brisbane", "cairns"}:
                content = correct_heat_load_output(location)
            elif not has_memory:
                content = incorrect_heat_load_output()
            elif location == "adelaide" and has_interference_episode:
                content = interfered_adelaide_heat_load_output()
            else:
                content = correct_heat_load_output(location)

        self._observations.append(
            {
                "task": task,
                "has_memory": has_memory,
                "feedback_count": len(feedback_files),
                "has_interference_episode": has_interference_episode,
                "has_verifier": (self.workspace / "tests").exists(),
            }
        )
        (self.workspace / "output.md").write_text(content, encoding="utf-8")
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
            usage_input_tokens=30,
            usage_output_tokens=15,
        )

    def adapter_name(self) -> str:
        return "direct"

    def resolved_model(self) -> str:
        return "fixed-test-model"


class CompositionStudyAdapter:
    def __init__(
        self,
        workspace: Path,
        *,
        headloss_output: str,
        power_output: str,
        composition_output: str,
        observations: list[dict[str, object]],
    ) -> None:
        self.workspace = workspace
        self._headloss_output = headloss_output
        self._power_output = power_output
        self._composition_output = composition_output
        self._observations = observations

    def execute(self, request: AdapterRequest) -> AdapterResult:
        instruction = (self.workspace / "instruction.md").read_text(encoding="utf-8")
        memory_path = self.workspace / ".aec-bench-learning" / "memory" / "components.json"
        memory = json.loads(memory_path.read_text(encoding="utf-8")) if memory_path.is_file() else {}
        component_entries = memory.get("components", {}) if isinstance(memory, dict) else {}
        components = tuple(sorted(component_entries)) if isinstance(component_entries, dict) else ()
        feedback_root = self.workspace / ".aec-bench-learning" / "feedback"
        feedback_count = sum(path.is_file() for path in feedback_root.rglob("*")) if feedback_root.is_dir() else 0

        if "friction head loss in a pressurised pipe" in instruction:
            task = "headloss"
            content = self._headloss_output
        elif "hydraulic pump power and shaft power" in instruction:
            task = "power"
            content = self._power_output
        elif "stormwater pump-station engineer" in instruction:
            task = "composition"
            content = selective_composition_output(self._composition_output, set(components))
        else:
            raise ValueError("unsupported A04 test task")

        self._observations.append(
            {
                "task": task,
                "components": components,
                "feedback_count": feedback_count,
                "has_verifier": (self.workspace / "tests").exists(),
            }
        )
        (self.workspace / "output.md").write_text(content, encoding="utf-8")
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
            usage_input_tokens=35,
            usage_output_tokens=18,
        )

    def adapter_name(self) -> str:
        return "direct"

    def resolved_model(self) -> str:
        return "fixed-test-model"


def selective_composition_output(golden_output: str, components: set[str]) -> str:
    """Return a target response whose correct fields reflect the available component memory."""

    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", golden_output, re.DOTALL)
    if not matches:
        raise ValueError("composition fixture has no final JSON output")
    payload = json.loads(matches[-1])
    if "headloss" not in components:
        payload["hazen_williams_loss_m"] = 0.0
        payload["rising_main_velocity_m_s"] = 0.0
    if "power" not in components:
        payload["hydraulic_power_kw"] = 0.0
        payload["motor_input_power_kw"] = 0.0
    if components != {"headloss", "power"}:
        payload["total_dynamic_head_m"] = 0.0
        payload["overall_pass_score"] = 0.0
    prefix = golden_output[: golden_output.rfind("```json")]
    return f"{prefix}```json\n{json.dumps(payload, indent=2, sort_keys=True)}\n```\n"


def upstream_invalidation_output(probe_output: str) -> str:
    """Return a parseable probe response that repeats the acquisition transition pattern."""

    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", probe_output, re.DOTALL)
    if not matches:
        raise ValueError("probe fixture has no final JSON output")
    payload = json.loads(matches[-1])
    payload["review_matrix"]["PRV-03"] = {
        "status": "fail",
        "evidence": "The acquisition response was reused and the current upstream revision was rejected.",
    }
    payload["review_matrix"]["PRV-06"] = {
        "status": "pass",
        "evidence": "The downstream propagation defect was not localized.",
    }
    payload["transition_decision"] = {
        "model_run": "non_governing",
        "model_report": "non_governing",
        "design_claim": "unsupported",
    }
    payload["findings"] = [
        {
            "item": "PRV-03",
            "severity": "critical",
            "source_id": "MANIFEST-03-042",
            "object_id": "RUN-03-042",
            "consequence": "The model run and report are treated as non-governing.",
            "action": "Update the model manifest before using the model evidence.",
        }
    ]
    prefix = probe_output[: probe_output.rfind("```json")]
    return f"{prefix}```json\n{json.dumps(payload, indent=2, sort_keys=True)}\n```\n"


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
    elif location == "adelaide":
        values = _heat_load_values(
            floor_area=150,
            area_per_person=5.0,
            outside_air_per_person=10.0,
            outdoor_temperature=39.6,
            outdoor_enthalpy=62.8,
            lighting_density=10,
            small_power_density=8,
            conduction_factor=15,
        )
    elif location == "cairns":
        values = _heat_load_values_for_airflow(
            floor_area=60,
            people=0.0,
            outside_air=60.0,
            outdoor_temperature=34.0,
            outdoor_enthalpy=81.4,
            lighting_density=5,
            small_power_density=250,
            conduction_factor=25,
        )
    else:
        raise ValueError(f"unsupported test location: {location}")
    return f"Calculation result\n\n```json\n{json.dumps(values, sort_keys=True)}\n```\n"


def incorrect_heat_load_output() -> str:
    return "Calculation result\n\n```json\n{}\n```\n"


def interfered_adelaide_heat_load_output() -> str:
    """Apply the server-room ventilation exception incorrectly to the occupied library."""

    values = _heat_load_values_for_airflow(
        floor_area=150,
        people=0.0,
        outside_air=150.0,
        outdoor_temperature=39.6,
        outdoor_enthalpy=62.8,
        lighting_density=10,
        small_power_density=8,
        conduction_factor=15,
    )
    return f"Calculation result\n\n```json\n{json.dumps(values, sort_keys=True)}\n```\n"


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
    return _heat_load_values_for_airflow(
        floor_area=floor_area,
        people=people,
        outside_air=outside_air,
        outdoor_temperature=outdoor_temperature,
        outdoor_enthalpy=outdoor_enthalpy,
        lighting_density=lighting_density,
        small_power_density=small_power_density,
        conduction_factor=conduction_factor,
    )


def _heat_load_values_for_airflow(
    *,
    floor_area: float,
    people: float,
    outside_air: float,
    outdoor_temperature: float,
    outdoor_enthalpy: float,
    lighting_density: float,
    small_power_density: float,
    conduction_factor: float,
) -> dict[str, float]:
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
