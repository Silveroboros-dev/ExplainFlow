from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from app.schemas.requests import AdvancedStreamRequest, ScriptPackRequest

ALLOWED_ARTIFACTS = {
    "thumbnail",
    "story_cards",
    "storyboard",
    "voiceover",
    "social_caption",
}


def artifact_scope_from_body(body: dict[str, Any]) -> list[str]:
    raw_scope = body.get("artifact_scope")
    if not isinstance(raw_scope, list):
        return []
    return [item for item in raw_scope if isinstance(item, str) and item in ALLOWED_ARTIFACTS]


def script_pack_request_from_body(body: dict[str, Any]) -> ScriptPackRequest:
    return ScriptPackRequest(
        source_text=body.get("source_text", "") if isinstance(body.get("source_text"), str) else "",
        source_manifest=body.get("source_manifest") if isinstance(body.get("source_manifest"), dict) else None,
        normalized_source_text=body.get("normalized_source_text", "") if isinstance(body.get("normalized_source_text"), str) else "",
        source_text_origin=body.get("source_text_origin") if isinstance(body.get("source_text_origin"), str) else None,
        content_signal=body.get("content_signal", {}) if isinstance(body.get("content_signal"), dict) else {},
        render_profile=body.get("render_profile", {}) if isinstance(body.get("render_profile"), dict) else {},
        artifact_scope=artifact_scope_from_body(body),
    )


def advanced_stream_request_from_body(body: dict[str, Any]) -> AdvancedStreamRequest:
    return AdvancedStreamRequest(
        source_text=body.get("source_text", "") if isinstance(body.get("source_text"), str) else "",
        source_manifest=body.get("source_manifest") if isinstance(body.get("source_manifest"), dict) else None,
        normalized_source_text=body.get("normalized_source_text", "") if isinstance(body.get("normalized_source_text"), str) else "",
        source_text_origin=body.get("source_text_origin") if isinstance(body.get("source_text_origin"), str) else None,
        content_signal=body.get("content_signal", {}) if isinstance(body.get("content_signal"), dict) else {},
        render_profile=body.get("render_profile", {}) if isinstance(body.get("render_profile"), dict) else {},
        script_pack=body.get("script_pack") if isinstance(body.get("script_pack"), dict) else None,
        script_pack_source_media_enriched=bool(body.get("script_pack_source_media_enriched")),
        artifact_scope=artifact_scope_from_body(body),
    )


def error_status_code(message: str, *, fallback: int = 500) -> int:
    normalized = message.strip().lower()
    if not normalized:
        return fallback
    if (
        normalized.startswith("provide ")
        or normalized.startswith("at least ")
        or normalized.startswith("missing ")
        or "unable to locate" in normalized
    ):
        return 400
    if normalized.startswith("unknown ") or "not found" in normalized:
        return 404
    return fallback


def service_response(result: dict[str, Any], *, error_fallback: int = 500):
    if result.get("status") != "error":
        return result
    return JSONResponse(
        status_code=error_status_code(str(result.get("message", "")), fallback=error_fallback),
        content=result,
    )


async def run_workflow_script_pack(
    *,
    workflow_id: str,
    script_request: ScriptPackRequest,
    coordinator: Any,
    agent: Any,
) -> dict[str, Any]:
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
