from __future__ import annotations

import os
from typing import Any, Callable

from clinicalclaw.engine import create_claw_agent

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.models import ScenarioSpec, ToolPolicy


def llm_ready() -> bool:
    return any(
        os.getenv(key)
        for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")
    )


def build_tool_gate(policy: ToolPolicy) -> Callable[[str, dict], bool]:
    allowed = set(policy.allowed_tools)
    blocked = set(policy.blocked_tools)

    def gate(tool_name: str, _: dict) -> bool:
        if allowed and tool_name not in allowed:
            return False
        if blocked and tool_name in blocked:
            return False
        return True

    return gate


def build_agent_for_scenario(
    settings: ClinicalClawSettings,
    scenario: ScenarioSpec,
    model: Any | None = None,
):
    agent = create_claw_agent(
        model=model or settings.default_model,
        instruction=(
            "You are ClinicalClaw, a hospital workflow execution assistant. "
            f"Execute the '{scenario.name}' scenario only. "
            "Stay inside the allowed tools and return structured, review-ready output."
        ),
        streaming=False,
        max_iterations=scenario.policy.max_iterations,
    )
    agent.before_tool = build_tool_gate(scenario.policy)
    return agent
