from __future__ import annotations

import json
from pathlib import Path

from clinicalclaw.models import ScenarioSpec


def load_scenarios(directory: str | Path) -> list[ScenarioSpec]:
    scenario_dir = Path(directory)
    if not scenario_dir.exists():
        return []

    scenarios: list[ScenarioSpec] = []
    for path in sorted(scenario_dir.glob("*.json")):
        scenarios.append(ScenarioSpec.model_validate_json(path.read_text(encoding="utf-8")))
    return scenarios


def load_scenario_map(directory: str | Path) -> dict[str, ScenarioSpec]:
    return {scenario.id: scenario for scenario in load_scenarios(directory)}

