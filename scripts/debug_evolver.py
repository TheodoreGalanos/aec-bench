# ABOUTME: Debug script to inspect raw evolver LLM responses.
# ABOUTME: Loads .env credentials via dotenv and calls the evolver with a sample prompt.

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os

from aec_bench.evolution.analysis import GraduatedScope
from aec_bench.evolution.mutation import _extract_json, _repair_json_strings
from aec_bench.evolution.prompts import (
    build_evolution_analysis_prompt,
    build_evolver_system_prompt,
)
from aec_bench.contracts.evolution import WorkspaceManifest
from aec_bench.providers.behavioral_llm import build_behavioral_llm_client

model = os.environ["AWS_SONNET_MODEL_ID"]
print(f"Evolver model: {model}")

evolver = build_behavioral_llm_client(model=model)
manifest = WorkspaceManifest(
    name="test", agent_adapter="rlm", evolvable_layers=["prompts", "skills"]
)
system_prompt = build_evolver_system_prompt(manifest)
analysis = build_evolution_analysis_prompt(
    batch_score=0.25,
    discipline_scores=[],
    patterns=[],
    scope=GraduatedScope.COMPREHENSIVE,
    field_failure_rates={
        "vc_mv_per_a_m": 1.0,
        "voltage_drop_v": 1.0,
        "voltage_drop_percent": 1.0,
    },
    workspace_skill_count=0,
    workspace_prompt_length=100,
)

full_prompt = system_prompt + "\n\n" + analysis
print(f"Prompt length: {len(full_prompt)} chars")
print()

response = evolver.complete(full_prompt, max_tokens=16384)
print(f"Response length: {len(response)} chars")
print()
print("=== RAW RESPONSE (first 2000 chars) ===")
print(repr(response[:2000]))
print("=== END ===")
print()

json_str = _extract_json(response)
print(f"Extracted JSON length: {len(json_str)} chars")
print()
print("=== EXTRACTED JSON (first 500 chars) ===")
print(repr(json_str[:500]))
print("=== END ===")
print()

# Try repair
import json

try:
    json.loads(json_str)
    print("JSON parses OK without repair")
except json.JSONDecodeError as e:
    print(f"JSON parse error: {e}")
    repaired = _repair_json_strings(json_str)
    print()
    print("=== REPAIRED JSON (first 500 chars) ===")
    print(repr(repaired[:500]))
    print("=== END ===")
    try:
        json.loads(repaired)
        print("Repaired JSON parses OK!")
    except json.JSONDecodeError as e2:
        print(f"Repaired JSON still fails: {e2}")
        # Show the area around the error
        pos = e2.pos or 0
        print(f"\nContext around error (pos {pos}):")
        print(repr(repaired[max(0, pos - 100):pos + 100]))
