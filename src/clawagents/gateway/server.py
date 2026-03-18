import json
import os
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

from clawagents.config.config import load_config, get_default_model
from clawagents.providers.llm import create_provider
from clawagents.process.command_queue import (
    enqueue_command_in_lane,
    get_queue_size,
    get_total_queue_size,
    get_active_task_count,
)
from clawagents.process.lanes import CommandLane
from clawagents.agent import create_claw_agent
from clawagents.gateway.ws import attach_websocket
from clinicalclaw.execution import ClinicalClawService

VALID_LANES = {"main", "cron", "subagent", "nested"}
_GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")


def _resolve_lane(raw: str | None) -> str:
    lane = (raw or "").strip().lower() or CommandLane.Main.value
    return lane if lane in VALID_LANES else CommandLane.Main.value


def _check_auth(request: Request) -> bool:
    if not _GATEWAY_API_KEY:
        return True
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:] == _GATEWAY_API_KEY
    return request.headers.get("x-api-key", "") == _GATEWAY_API_KEY


def create_app() -> tuple:
    config = load_config()
    active_model = get_default_model(config)
    llm = create_provider(active_model, config)
    clinicalclaw = ClinicalClawService()

    # Pre-build a shared registry for agent reuse
    _shared_registry = None

    app = FastAPI(title="ClawAgents Gateway")

    cors_origins = os.getenv("GATEWAY_CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "provider": llm.name,
            "model": active_model,
            "clinicalclaw": {
                "scenario_count": len(clinicalclaw.scenario_map),
            },
        }

    @app.get("/queue")
    async def queue_status():
        lanes = {lane: get_queue_size(lane) for lane in VALID_LANES}
        return {
            "lanes": lanes,
            "total": get_total_queue_size(),
            "active": get_active_task_count(),
        }

    @app.post("/chat")
    async def chat(request: Request):
        if not _check_auth(request):
            return Response(
                content=json.dumps({"error": "Unauthorized. Set Authorization: Bearer <GATEWAY_API_KEY>"}),
                status_code=401,
                media_type="application/json",
            )

        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "task": "...", "lane": "main|cron|subagent", "scenario_id": "optional" }'}),
                status_code=400,
                media_type="application/json",
            )

        task = payload.get("task", "Unknown task")
        lane = _resolve_lane(payload.get("lane"))
        scenario_id = payload.get("scenario_id")
        requested_by = payload.get("requested_by", "http-chat")
        case_id = payload.get("case_id")
        external_patient_id = payload.get("external_patient_id")
        note = payload.get("note")

        async def execute_graph():
            print(f"[Gateway] lane={lane} task: {task}")
            if scenario_id:
                if not clinicalclaw.get_scenario(scenario_id):
                    raise ValueError(f"Unknown scenario_id: {scenario_id}")
                return await clinicalclaw.invoke_scenario(
                    task=task,
                    scenario_id=scenario_id,
                    llm=llm,
                    requested_by=requested_by,
                    case_id=case_id,
                    external_patient_id=external_patient_id,
                    note=note,
                )
            agent = create_claw_agent(model=llm)
            return await agent.invoke(task)

        try:
            result = await enqueue_command_in_lane(lane, execute_graph)
            if scenario_id:
                success = result.result.status != "reauth_required"
                return {
                    "success": success,
                    "lane": lane,
                    "scenario_id": result.scenario.id,
                    "task_run_id": result.task_run_id,
                    "review_required": result.review_required,
                    "artifact_ids": result.artifact_ids,
                    "access_event_ids": result.access_event_ids,
                    "status": result.result.status,
                    "result": result.result.result,
                    "iterations": result.result.iterations,
                }
            return {
                "success": True,
                "lane": lane,
                "status": result.status,
                "result": result.result,
                "iterations": result.iterations,
            }
        except Exception as e:
            return Response(
                content=json.dumps({"success": False, "lane": lane, "error": str(e)}),
                status_code=500,
                media_type="application/json",
            )

    @app.post("/chat/stream")
    async def chat_stream(request: Request):
        if not _check_auth(request):
            return Response(
                content=json.dumps({"error": "Unauthorized"}),
                status_code=401,
                media_type="application/json",
            )

        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "task": "...", "lane": "main|cron|subagent", "scenario_id": "optional" }'}),
                status_code=400,
                media_type="application/json",
            )

        task = payload.get("task", "Unknown task")
        lane = _resolve_lane(payload.get("lane"))
        scenario_id = payload.get("scenario_id")
        requested_by = payload.get("requested_by", "http-stream")
        case_id = payload.get("case_id")
        external_patient_id = payload.get("external_patient_id")
        note = payload.get("note")

        import asyncio

        event_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def sse(event: str, data: Any):
            event_queue.put_nowait(f"event: {event}\ndata: {json.dumps(data)}\n\n")

        async def _run():
            sse("queued", {"lane": lane, "position": get_queue_size(lane), "scenario_id": scenario_id})
            try:
                result = await enqueue_command_in_lane(lane, _execute)
                if scenario_id:
                    success = result.result.status != "reauth_required"
                    sse("done", {
                        "success": success,
                        "lane": lane,
                        "scenario_id": result.scenario.id,
                        "task_run_id": result.task_run_id,
                        "review_required": result.review_required,
                        "artifact_ids": result.artifact_ids,
                        "access_event_ids": result.access_event_ids,
                        "status": result.result.status,
                        "result": result.result.result,
                        "iterations": result.result.iterations,
                    })
                else:
                    sse("done", {
                        "lane": lane,
                        "status": result.status,
                        "result": result.result,
                        "iterations": result.iterations,
                    })
            except Exception as e:
                sse("error", {"lane": lane, "error": str(e)})
            finally:
                event_queue.put_nowait(None)

        async def _execute():
            sse("started", {"lane": lane, "scenario_id": scenario_id})
            if scenario_id:
                if not clinicalclaw.get_scenario(scenario_id):
                    raise ValueError(f"Unknown scenario_id: {scenario_id}")

                def on_event(kind, data):
                    sse("agent", {"kind": kind, "data": data})

                return await clinicalclaw.invoke_scenario(
                    task=task,
                    scenario_id=scenario_id,
                    llm=llm,
                    requested_by=requested_by,
                    case_id=case_id,
                    external_patient_id=external_patient_id,
                    note=note,
                    on_event=on_event,
                )

            agent = create_claw_agent(model=llm)

            def on_event(kind, data):
                sse("agent", {"kind": kind, "data": data})

            return await agent.invoke(task, on_event=on_event)

        asyncio.create_task(_run())

        async def _stream():
            while True:
                msg = await event_queue.get()
                if msg is None:
                    break
                yield msg

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    attach_websocket(app, llm, _GATEWAY_API_KEY, clinicalclaw)

    return app, llm, active_model


def start_gateway(port: int = 3000):
    app, llm, active_model = create_app()
    auth_status = "enabled" if _GATEWAY_API_KEY else "disabled (set GATEWAY_API_KEY to enable)"
    print(f"\n🦞 ClawAgents Gateway running on http://localhost:{port}")
    print(f"   Provider: {llm.name}")
    print(f"   Model: {active_model}")
    print(f"   Auth: {auth_status}")
    print("   Endpoints: POST /chat | POST /chat/stream | WS /ws | GET /queue | GET /health\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
