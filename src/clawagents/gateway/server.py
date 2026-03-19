import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
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
from clinicalclaw.demo_workspace import demo_workspace_store
from clinicalclaw.console_workspace import console_snapshot, route_general_query
from clinicalclaw.console_agent import build_console_agent, build_routed_task, route_with_llm
from clinicalclaw.execution import ClinicalClawService
from clinicalclaw.findings_closure import findings_closure_store
from clinicalclaw.missed_diagnosis import missed_diagnosis_store
from clinicalclaw.queue_triage import queue_triage_store
from clinicalclaw.safety_monitor import safety_monitor_store

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
    demo_root = Path(__file__).resolve().parents[2] / "clinicalclaw" / "ui" / "demo"
    demo_index = demo_root / "index.html"
    safety_root = Path(__file__).resolve().parents[2] / "clinicalclaw" / "ui" / "safety"
    safety_index = safety_root / "index.html"
    findings_root = Path(__file__).resolve().parents[2] / "clinicalclaw" / "ui" / "findings"
    findings_index = findings_root / "index.html"

    cors_origins = os.getenv("GATEWAY_CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if demo_root.exists():
        app.mount("/demo-assets", StaticFiles(directory=str(demo_root)), name="demo-assets")
    if safety_root.exists():
        app.mount("/safety-assets", StaticFiles(directory=str(safety_root)), name="safety-assets")
    if findings_root.exists():
        app.mount("/findings-assets", StaticFiles(directory=str(findings_root)), name="findings-assets")

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

    @app.get("/")
    async def root():
        return RedirectResponse(url="/demo", status_code=307)

    @app.get("/demo")
    async def demo_page():
        if not demo_index.exists():
            return Response(content="Demo UI is not available.", status_code=404)
        return FileResponse(demo_index)

    @app.get("/api/demo/workspace")
    async def demo_workspace():
        return demo_workspace_store.snapshot()

    @app.get("/api/demo/console")
    async def demo_console():
        return console_snapshot()

    @app.get("/api/demo/cases/{case_id}")
    async def demo_case(case_id: str):
        try:
            return demo_workspace_store.get_case(case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown demo case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/demo/chat")
    async def demo_chat(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "message": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        message = (payload.get("message") or "").strip()
        if not case_id or not message:
            return Response(
                content=json.dumps({"error": "case_id and message are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return demo_workspace_store.chat(case_id=case_id, message=message)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown demo case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/demo/command")
    async def demo_command(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "message": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        message = (payload.get("message") or "").strip()
        if not message:
            return Response(
                content=json.dumps({"error": "message is required"}),
                status_code=400,
                media_type="application/json",
            )
        return route_general_query(message)

    @app.post("/api/demo/execute-stream")
    async def demo_execute_stream(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "message": "...", "lane": "optional" }'}),
                status_code=400,
                media_type="application/json",
            )

        message = (payload.get("message") or "").strip()
        lane = _resolve_lane(payload.get("lane"))
        if not message:
            return Response(
                content=json.dumps({"error": "message is required"}),
                status_code=400,
                media_type="application/json",
            )

        import asyncio

        event_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def sse(event: str, data: Any):
            event_queue.put_nowait(f"event: {event}\ndata: {json.dumps(data)}\n\n")

        async def _run():
            route = await route_with_llm(llm, message)
            sse(
                "routed",
                {
                    "workflow_id": route["workflow_id"],
                    "target_module": route["target_module"],
                    "suggested_module": route.get("suggested_module"),
                    "confidence": route["confidence"],
                    "reason": route["reason"],
                    "next_action": route["next_action"],
                    "alternatives": route.get("alternatives", []),
                    "fallback": route["fallback"],
                },
            )
            sse("queued", {"lane": lane, "position": get_queue_size(lane)})

            async def _execute():
                sse("started", {"lane": lane, "workflow_id": route["workflow_id"]})
                agent = build_console_agent(llm)

                def on_event(kind, data):
                    sse("agent", {"kind": kind, "data": data})

                task = build_routed_task(route, message)
                return await agent.invoke(task, on_event=on_event)

            try:
                result = await enqueue_command_in_lane(lane, _execute)
                sse(
                    "done",
                    {
                        "lane": lane,
                        "workflow_id": route["workflow_id"],
                        "target_module": route["target_module"],
                        "suggested_module": route.get("suggested_module"),
                        "status": result.status,
                        "result": result.result,
                        "iterations": result.iterations,
                    },
                )
            except Exception as e:
                sse("error", {"lane": lane, "error": str(e)})
            finally:
                event_queue.put_nowait(None)

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

    @app.post("/api/demo/upload")
    async def demo_upload(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "filename": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        filename = (payload.get("filename") or "").strip()
        if not case_id or not filename:
            return Response(
                content=json.dumps({"error": "case_id and filename are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return demo_workspace_store.add_upload(case_id=case_id, filename=filename)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown demo case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/demo/review")
    async def demo_review(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "action": "...", "comment": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        action = (payload.get("action") or "").strip()
        comment = (payload.get("comment") or "").strip() or None
        if not case_id or not action:
            return Response(
                content=json.dumps({"error": "case_id and action are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return demo_workspace_store.review(case_id=case_id, action=action, comment=comment)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown demo case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.get("/safety-demo")
    async def safety_demo_page():
        if not safety_index.exists():
            return Response(content="Safety demo UI is not available.", status_code=404)
        return FileResponse(safety_index)

    @app.get("/findings-demo")
    async def findings_demo_page():
        if not findings_index.exists():
            return Response(content="Findings demo UI is not available.", status_code=404)
        return FileResponse(findings_index)

    @app.get("/api/findings/workspace")
    async def findings_workspace():
        return findings_closure_store.snapshot()

    @app.get("/api/findings/cases/{case_id}")
    async def findings_case(case_id: str):
        try:
            return findings_closure_store.get_case(case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown findings case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/findings/rerun")
    async def findings_rerun(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        if not case_id:
            return Response(
                content=json.dumps({"error": "case_id is required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return findings_closure_store.rerun(case_id=case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown findings case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/findings/review")
    async def findings_review(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "action": "...", "comment": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        action = (payload.get("action") or "").strip()
        comment = (payload.get("comment") or "").strip() or None
        if not case_id or not action:
            return Response(
                content=json.dumps({"error": "case_id and action are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return findings_closure_store.review(case_id=case_id, action=action, comment=comment)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown findings case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/findings/explain")
    async def findings_explain(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "question": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        question = (payload.get("question") or "").strip()
        if not case_id or not question:
            return Response(
                content=json.dumps({"error": "case_id and question are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return findings_closure_store.explain(case_id=case_id, question=question)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown findings case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.get("/api/queue/workspace")
    async def queue_workspace():
        return queue_triage_store.snapshot()

    @app.get("/api/queue/cases/{case_id}")
    async def queue_case(case_id: str):
        try:
            return queue_triage_store.get_case(case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown queue case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/queue/rerun")
    async def queue_rerun(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        if not case_id:
            return Response(
                content=json.dumps({"error": "case_id is required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return queue_triage_store.rerun(case_id=case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown queue case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/queue/review")
    async def queue_review(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "action": "...", "comment": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        action = (payload.get("action") or "").strip()
        comment = (payload.get("comment") or "").strip() or None
        if not case_id or not action:
            return Response(
                content=json.dumps({"error": "case_id and action are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return queue_triage_store.review(case_id=case_id, action=action, comment=comment)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown queue case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/queue/explain")
    async def queue_explain(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "question": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        question = (payload.get("question") or "").strip()
        if not case_id or not question:
            return Response(
                content=json.dumps({"error": "case_id and question are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return queue_triage_store.explain(case_id=case_id, question=question)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown queue case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.get("/api/diagnosis/workspace")
    async def diagnosis_workspace():
        return missed_diagnosis_store.snapshot()

    @app.get("/api/diagnosis/cases/{case_id}")
    async def diagnosis_case(case_id: str):
        try:
            return missed_diagnosis_store.get_case(case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown diagnosis case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/diagnosis/rerun")
    async def diagnosis_rerun(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        if not case_id:
            return Response(
                content=json.dumps({"error": "case_id is required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return missed_diagnosis_store.rerun(case_id=case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown diagnosis case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/diagnosis/review")
    async def diagnosis_review(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "action": "...", "comment": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        action = (payload.get("action") or "").strip()
        comment = (payload.get("comment") or "").strip() or None
        if not case_id or not action:
            return Response(
                content=json.dumps({"error": "case_id and action are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return missed_diagnosis_store.review(case_id=case_id, action=action, comment=comment)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown diagnosis case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/diagnosis/explain")
    async def diagnosis_explain(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "question": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        question = (payload.get("question") or "").strip()
        if not case_id or not question:
            return Response(
                content=json.dumps({"error": "case_id and question are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return missed_diagnosis_store.explain(case_id=case_id, question=question)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown diagnosis case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.get("/api/safety/workspace")
    async def safety_workspace():
        return safety_monitor_store.snapshot()

    @app.get("/api/safety/cases/{case_id}")
    async def safety_case(case_id: str):
        try:
            return safety_monitor_store.get_case(case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown safety case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/safety/rerun")
    async def safety_rerun(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        if not case_id:
            return Response(
                content=json.dumps({"error": "case_id is required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return safety_monitor_store.rerun(case_id=case_id)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown safety case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/safety/review")
    async def safety_review(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "action": "...", "comment": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        action = (payload.get("action") or "").strip()
        comment = (payload.get("comment") or "").strip() or None
        if not case_id or not action:
            return Response(
                content=json.dumps({"error": "case_id and action are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return safety_monitor_store.review(case_id=case_id, action=action, comment=comment)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown safety case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

    @app.post("/api/safety/explain")
    async def safety_explain(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": 'Invalid JSON. Send { "case_id": "...", "question": "..." }'}),
                status_code=400,
                media_type="application/json",
            )
        case_id = payload.get("case_id")
        question = (payload.get("question") or "").strip()
        if not case_id or not question:
            return Response(
                content=json.dumps({"error": "case_id and question are required"}),
                status_code=400,
                media_type="application/json",
            )
        try:
            return safety_monitor_store.explain(case_id=case_id, question=question)
        except KeyError:
            return Response(
                content=json.dumps({"error": f"Unknown safety case: {case_id}"}),
                status_code=404,
                media_type="application/json",
            )

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
