from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinicalclaw.engine import create_claw_agent
from clinicalclaw.engine.providers.llm import LLMMessage, LLMProvider
from clinicalclaw.engine.tools.registry import ToolResult
from clinicalclaw.console_workspace import WORKFLOWS, rank_workflows, route_general_query
from clinicalclaw.demo_workspace import demo_workspace_store
from clinicalclaw.safety_monitor import KNOWLEDGE_BASE, safety_monitor_store

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = str(REPO_ROOT / "skills")


class WorkflowCatalogTool:
    name = "workflow_catalog"
    description = "Return the available ClinicalClaw workflows, their module ids, and supported tools."
    parameters: dict[str, dict[str, Any]] = {}
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=json.dumps(WORKFLOWS, indent=2))


class NeuroWorkspaceTool:
    name = "get_neuro_workspace"
    description = "Return the current neuro longitudinal review workspace, patient summary, trend metrics, and report state."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional neuro case id. Defaults to the main mock longitudinal case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        case_id = args.get("case_id") or demo_workspace_store.snapshot()["default_case_id"]
        payload = demo_workspace_store.get_case(case_id)
        compact = {
            "id": payload["id"],
            "title": payload["title"],
            "patient": payload["patient"],
            "analysis": payload["analysis"],
            "report": {
                "title": payload["report"]["title"],
                "summary": payload["report"]["summary"],
                "risk_level": payload["report"]["risk_level"],
            },
            "timeline": payload["timeline"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class SafetyQueueTool:
    name = "get_safety_queue"
    description = "Return the current radiation safety queue summary and the incoming cases with risk tiers."
    parameters: dict[str, dict[str, Any]] = {}
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = safety_monitor_store.snapshot()
        compact = {
            "queue_summary": payload["queue_summary"],
            "cases": payload["cases"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class SafetyCaseTool:
    name = "get_safety_case"
    description = "Return a specific safety case with intake, top match, mitigation playbook, review questions, and review state."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Safety case id to inspect. Defaults to the first incoming case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        case_id = args.get("case_id") or safety_monitor_store.snapshot()["default_case_id"]
        payload = safety_monitor_store.get_case(case_id)
        compact = {
            "id": payload["id"],
            "title": payload["title"],
            "risk_label": payload["risk_label"],
            "risk_reason": payload["risk_reason"],
            "fields": payload["fields"],
            "playbook": payload["playbook"],
            "review_questions": payload["review_questions"],
            "matched_incidents": payload["matched_incidents"][:3],
            "review": payload["review"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class SafetyKnowledgeSearchTool:
    name = "search_safety_knowledge"
    description = "Search the local radiation safety knowledge base for failure modes relevant to a query."
    parameters = {
        "query": {
            "type": "string",
            "description": "User query or short description of a safety concern.",
            "required": True,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        query = (args.get("query") or "").lower()
        if not query:
            return ToolResult(success=False, output="", error="query is required")
        ranked: list[dict[str, Any]] = []
        for item in KNOWLEDGE_BASE:
            haystack = " ".join(
                [
                    item["title"],
                    item["summary"],
                    item["category"],
                    item["process_step"],
                    " ".join(item["signals"]),
                    " ".join(item["tags"]),
                ]
            ).lower()
            score = sum(1 for token in query.split() if token and token in haystack)
            if score:
                ranked.append(
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "category": item["category"],
                        "process_step": item["process_step"],
                        "score": score,
                        "source": item["source"],
                    }
                )
        ranked.sort(key=lambda entry: entry["score"], reverse=True)
        return ToolResult(success=True, output=json.dumps(ranked[:5], indent=2))


def _extract_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


async def route_with_llm(llm: LLMProvider, message: str) -> dict[str, Any]:
    ranked = rank_workflows(message)
    heuristic_alternatives = [
        {"module": item["module"], "title": item["workflow"]["title"], "score": item["score"]}
        for item in ranked
        if item["score"] > 0
    ]
    system_prompt = (
        "You are the ClinicalClaw router. "
        "Classify the user's request into one workflow_id from "
        "general_chat, neuro_longitudinal, radiation_safety_monitor. "
        "Return strict JSON with keys: workflow_id, confidence, reason, next_action, alternatives. "
        "alternatives must be an array of 0-2 workflow_id values that are also plausible. "
        "If uncertain, choose general_chat."
    )
    user_prompt = (
        "User request:\n"
        f"{message}\n\n"
        "Workflow boundaries:\n"
        "- neuro_longitudinal: MRI, hippocampus, atrophy, trend, longitudinal imaging report\n"
        "- radiation_safety_monitor: incident, QA, alert, radiation, dosimetry, timeout, adaptive planning\n"
        "- general_chat: anything else or uncertain\n"
    )
    try:
        response = await llm.chat(
            [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
        )
        parsed = _extract_json(response.content)
        if parsed and parsed.get("workflow_id") in {
            "general_chat",
            "neuro_longitudinal",
            "radiation_safety_monitor",
        }:
            workflow_id = parsed["workflow_id"]
            module_map = {
                "general_chat": "home",
                "neuro_longitudinal": "neuro",
                "radiation_safety_monitor": "safety",
            }
            workflow = next(item for item in WORKFLOWS if item["id"] == workflow_id)
            confidence = float(parsed.get("confidence", 0.0) or 0.0)
            suggested_module = module_map[workflow_id] if workflow_id != "general_chat" else None
            target_module = module_map[workflow_id]
            if workflow_id != "general_chat" and confidence < 0.6:
                target_module = "home"
            parsed_alternatives = parsed.get("alternatives") or []
            alternatives = []
            for alt in parsed_alternatives:
                if alt in {"general_chat", "neuro_longitudinal", "radiation_safety_monitor"} and alt != workflow_id:
                    alt_wf = next(item for item in WORKFLOWS if item["id"] == alt)
                    alternatives.append({"module": alt_wf["module"], "title": alt_wf["title"]})
            if not alternatives:
                alternatives = [
                    {"module": item["module"], "title": item["title"]}
                    for item in heuristic_alternatives
                    if item["module"] != suggested_module
                ][:2]
            return {
                "workflow_id": workflow_id,
                "workflow": workflow,
                "target_module": target_module,
                "suggested_module": suggested_module,
                "confidence": confidence,
                "reason": parsed.get("reason", "Router selected the closest workflow."),
                "next_action": parsed.get("next_action", "Open the selected module."),
                "alternatives": alternatives,
                "fallback": False,
            }
    except Exception:
        pass

    fallback = route_general_query(message)
    workflow = fallback["workflow"]
    return {
        "workflow_id": workflow["id"],
        "workflow": workflow,
        "target_module": fallback["target_module"],
        "suggested_module": fallback["target_module"] if fallback["target_module"] != "home" else None,
        "confidence": 0.0,
        "reason": fallback["assistant"]["content"],
        "next_action": "Use the recommended workflow or stay in general chat.",
        "alternatives": [
            {"module": item["module"], "title": item["title"]}
            for item in fallback.get("alternatives", [])
        ],
        "fallback": True,
    }


def build_console_agent(llm: LLMProvider):
    tools = [
        WorkflowCatalogTool(),
        NeuroWorkspaceTool(),
        SafetyQueueTool(),
        SafetyCaseTool(),
        SafetyKnowledgeSearchTool(),
    ]
    instruction = (
        "You are the ClinicalClaw console agent. "
        "Help the user accomplish clinical workflow tasks using the available tools. "
        "Be concise, grounded, and operational. "
        "Before producing any user-facing report, summary, or polished chat answer, you must first call "
        "use_skill for the required presentation skill or skills. "
        "Always load clinical_report_presentation first. "
        "If the workflow is neuro_longitudinal, also load neuro_report_presenter. "
        "If the workflow is radiation_safety_monitor, also load safety_brief_presenter. "
        "Silently organize your facts before writing, but never reveal hidden planning or chain-of-thought. "
        "For neuro requests, inspect the neuro workspace before answering. "
        "For safety requests, inspect the safety queue or a safety case before answering. "
        "Do not invent patient data or incident details. "
        "Do not expose internal tool names or routing details in the final answer. "
        "Summarize what you found and recommend the next action clearly."
    )
    agent = create_claw_agent(
        model=llm,
        instruction=instruction,
        tools=tools,
        skills=[SKILLS_DIR],
        streaming=True,
    )
    agent.allow_only_tools(
        "think",
        "write_todos",
        "update_todo",
        "list_skills",
        "use_skill",
        "workflow_catalog",
        "get_neuro_workspace",
        "get_safety_queue",
        "get_safety_case",
        "search_safety_knowledge",
    )
    return agent


def build_routed_task(route: dict[str, Any], message: str) -> str:
    workflow_id = route["workflow_id"]
    if workflow_id == "neuro_longitudinal":
        return (
            "Workflow: neuro_longitudinal\n"
            "Required pre-answer tool calls:\n"
            "1. use_skill(name='clinical_report_presentation')\n"
            "2. use_skill(name='neuro_report_presenter')\n"
            "Use the neuro workspace tools to inspect the longitudinal MRI case before answering.\n"
            "Present the final answer as a polished clinician-facing markdown brief with sections for MRI Trend Analysis, "
            "Draft Physician Summary, Recommendations, and a one-line Risk Tier.\n"
            f"User request: {message}"
        )
    if workflow_id == "radiation_safety_monitor":
        return (
            "Workflow: radiation_safety_monitor\n"
            "Required pre-answer tool calls:\n"
            "1. use_skill(name='clinical_report_presentation')\n"
            "2. use_skill(name='safety_brief_presenter')\n"
            "Use the safety queue and safety case tools before answering. "
            "If incident pattern matching is relevant, search the local safety knowledge base.\n"
            "Present the final answer as a polished clinical operations brief with sections for Risk Summary, "
            "Matched Failure Patterns, Recommended Checks, and a one-line Escalation.\n"
            f"User request: {message}"
        )
    return (
        "Workflow: general_chat\n"
        "Use the clinical_report_presentation skill before the final answer.\n"
        "Use the workflow catalog and any relevant module tool if it helps clarify the user's request.\n"
        "Keep the final answer concise and product-ready, without exposing internal tool or routing names.\n"
        f"User request: {message}"
    )
