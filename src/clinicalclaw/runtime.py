from __future__ import annotations

import os

from clawagents import create_claw_agent

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.models import ScenarioSpec


def llm_ready() -> bool:
    return any(
        os.getenv(key)
        for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")
    )


def build_agent_for_scenario(settings: ClinicalClawSettings, scenario: ScenarioSpec):
    agent = create_claw_agent(
        model=settings.default_model,
        instruction=(
            "You are ClinicalClaw, a hospital workflow execution assistant. "
            "Stay inside the allowed tools and return structured, review-ready output."
        ),
        streaming=False,
    )
    if scenario.policy.allowed_tools:
        agent.allow_only_tools(*scenario.policy.allowed_tools)
    if scenario.policy.blocked_tools:
        agent.block_tools(*scenario.policy.blocked_tools)
    return agent

