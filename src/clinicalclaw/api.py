from __future__ import annotations

from fastapi import FastAPI, HTTPException

from clinicalclaw.config import load_settings
from clinicalclaw.models import CreateTaskRunRequest
from clinicalclaw.runtime import llm_ready
from clinicalclaw.scenarios import load_scenario_map
from clinicalclaw.store import MemoryStore


def create_app() -> FastAPI:
    settings = load_settings()
    scenario_map = load_scenario_map(settings.scenario_dir)
    store = MemoryStore()
    store.bootstrap_demo_data(list(scenario_map.values()))

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Week 1 shell platform for modular clinical AI execution",
    )

    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "environment": settings.environment,
            "api_prefix": settings.api_prefix,
            "scenario_count": len(scenario_map),
        }

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.environment,
            "llm_ready": llm_ready(),
            "scenario_count": len(scenario_map),
        }

    @app.get(f"{settings.api_prefix}/scenarios")
    async def list_scenarios():
        return list(scenario_map.values())

    @app.get(f"{settings.api_prefix}/scenarios/{{scenario_id}}")
    async def get_scenario(scenario_id: str):
        scenario = scenario_map.get(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return scenario

    @app.get(f"{settings.api_prefix}/policies")
    async def list_policies():
        return {
            scenario_id: scenario.policy
            for scenario_id, scenario in scenario_map.items()
        }

    @app.get(f"{settings.api_prefix}/cases")
    async def list_cases():
        return list(store.cases.values())

    @app.get(f"{settings.api_prefix}/tasks")
    async def list_tasks():
        return list(store.tasks.values())

    @app.post(f"{settings.api_prefix}/tasks")
    async def create_task(request: CreateTaskRunRequest):
        if request.scenario_id not in scenario_map:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return store.create_task(request, scenario_map)

    @app.get(f"{settings.api_prefix}/artifacts")
    async def list_artifacts():
        return list(store.artifacts.values())

    @app.get(f"{settings.api_prefix}/access-events")
    async def list_access_events():
        return list(store.access_events.values())

    return app

