import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.schemas.requests import (
    SignalExtractionRequest,
    WorkflowArtifactLockRequest,
    WorkflowAgentChatRequest,
    WorkflowRenderLockRequest,
    WorkflowStartRequest,
    WorkflowStreamRequest,
)
from app.services import AgentCoordinator, GeminiStoryAgent, WorkflowChatAgent

router = APIRouter()
agent = GeminiStoryAgent()
coordinator = AgentCoordinator()
chat_agent = WorkflowChatAgent(coordinator=coordinator, story_agent=agent)


def _handle_error(exc: Exception, status_code: int = 409) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=status_code, detail=str(exc))


@router.post("/workflow/start")
async def workflow_start(payload: WorkflowStartRequest):
    snapshot = await coordinator.start_workflow(
        payload.source_text,
        payload.source_manifest.model_dump() if payload.source_manifest is not None else None,
        payload.normalized_source_text,
        payload.source_text_origin,
    )
    return {
        "status": "success",
        "workflow_id": str(snapshot["workflow_id"]),
        "workflow": snapshot,
    }


@router.post("/workflow/{workflow_id}/extract-signal")
async def workflow_extract_signal(workflow_id: str, payload: WorkflowStartRequest):
    try:
        extraction_result = await agent.extract_signal(
            SignalExtractionRequest(
                input_text=payload.source_text,
                source_manifest=payload.source_manifest,
                normalized_source_text=payload.normalized_source_text,
                source_text_origin=payload.source_text_origin,
            )
        )
        updated_snapshot = await coordinator.record_signal_result(
            workflow_id,
            source_text=payload.source_text,
            source_manifest=payload.source_manifest.model_dump() if payload.source_manifest is not None else None,
            normalized_source_text=str(extraction_result.get("normalized_source_text", payload.normalized_source_text or "")),
            source_text_origin=str(extraction_result.get("source_text_origin", payload.source_text_origin or "")) or None,
            result=extraction_result,
        )
        response: dict[str, Any] = {
            "workflow_id": workflow_id,
            "workflow": updated_snapshot,
            "status": extraction_result.get("status", "error"),
        }
        if extraction_result.get("status") == "success":
            response["content_signal"] = extraction_result.get("content_signal", {})
        else:
            response["message"] = extraction_result.get("message", "Signal extraction failed")
        if isinstance(extraction_result.get("trace"), dict):
            response["extraction_trace"] = extraction_result["trace"]
        return response
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/workflow/{workflow_id}")
async def workflow_snapshot(workflow_id: str):
    try:
        return await coordinator.get_snapshot(workflow_id)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/workflow/{workflow_id}/lock-artifacts")
async def workflow_lock_artifacts(workflow_id: str, payload: WorkflowArtifactLockRequest):
    try:
        snapshot = await coordinator.lock_artifacts(workflow_id, payload.artifact_scope)
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "workflow": snapshot,
        }
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/workflow/{workflow_id}/lock-render")
async def workflow_lock_render(workflow_id: str, payload: WorkflowRenderLockRequest):
    try:
        snapshot = await coordinator.lock_render_profile(workflow_id, payload.render_profile)
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "workflow": snapshot,
        }
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/workflow/{workflow_id}/generate-script-pack")
async def workflow_generate_script_pack(workflow_id: str):
    try:
        script_request = await coordinator.build_script_pack_request(workflow_id)
        result = await agent.generate_script_pack_advanced(script_request)
        snapshot = await coordinator.record_script_pack_result(workflow_id, result)
        response: dict[str, Any] = {
            "workflow_id": workflow_id,
            "workflow": snapshot,
            "status": result.get("status", "error"),
        }
        if result.get("status") == "success":
            response["script_pack"] = result.get("script_pack", {})
            if isinstance(result.get("claim_traceability"), dict):
                response["claim_traceability"] = result["claim_traceability"]
            if isinstance(result.get("planner_qa_summary"), dict):
                response["planner_qa_summary"] = result["planner_qa_summary"]
        else:
            response["message"] = result.get("message", "Script pack generation failed")
        if isinstance(result.get("trace"), dict):
            response["script_trace"] = result["trace"]
        return response
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/workflow/{workflow_id}/generate-stream")
async def workflow_generate_stream(workflow_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    stream_request = WorkflowStreamRequest(
        script_pack=body.get("script_pack") if isinstance(body.get("script_pack"), dict) else None,
    )

    try:
        advanced_request = await coordinator.build_stream_request(
            workflow_id,
            script_pack_override=stream_request.script_pack,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc

    async def event_generator():
        recorded_result = False
        async for event in agent.generate_stream_advanced_events(
            request=request,
            payload=advanced_request,
        ):
            event_name = event.get("event", "")
            if event_name == "final_bundle_ready":
                try:
                    payload_obj = json.loads(event.get("data", "{}"))
                    run_id = payload_obj.get("run_id")
                    bundle_url = payload_obj.get("bundle_url")
                    await coordinator.record_stream_result(
                        workflow_id,
                        success=True,
                        run_id=run_id if isinstance(run_id, str) else None,
                        bundle_url=bundle_url if isinstance(bundle_url, str) else None,
                    )
                    recorded_result = True
                except Exception:
                    pass
            elif event_name == "error":
                try:
                    payload_obj = json.loads(event.get("data", "{}"))
                    error_text = payload_obj.get("error")
                    await coordinator.record_stream_result(
                        workflow_id,
                        success=False,
                        error=str(error_text or "Stream generation failed"),
                    )
                    recorded_result = True
                except Exception:
                    pass
            yield event

        if not recorded_result:
            try:
                await coordinator.record_stream_result(
                    workflow_id,
                    success=False,
                    error="Stream ended without a terminal event.",
                )
            except Exception:
                pass

    return EventSourceResponse(event_generator())


@router.post("/workflow/agent/chat")
async def workflow_agent_chat(payload: WorkflowAgentChatRequest):
    try:
        response = await chat_agent.handle_chat_turn(payload)
        return response.model_dump()
    except Exception as exc:
        raise _handle_error(exc, status_code=500) from exc
