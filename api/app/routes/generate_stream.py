import asyncio
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.schemas.requests import (
    AdvancedStreamRequest,
    QuickArtifactOverrideRequest,
    QuickArtifactRequest,
    QuickBlockOverrideRequest,
    QuickReelRequest,
    QuickSourceIndexRequest,
    RegenerateSceneRequest,
    ScriptPackRequest,
    SignalExtractionRequest,
)
from app.services import GeminiStoryAgent

router = APIRouter()
agent = GeminiStoryAgent()
QUICK_INDEX_JOBS: dict[str, dict] = {}

ALLOWED_ARTIFACTS = {
    "thumbnail",
    "story_cards",
    "storyboard",
    "voiceover",
    "social_caption",
}


def _artifact_scope_from_body(body: dict) -> list[str]:
    raw_scope = body.get("artifact_scope")
    if not isinstance(raw_scope, list):
        return []
    return [item for item in raw_scope if isinstance(item, str) and item in ALLOWED_ARTIFACTS]


async def _run_quick_source_index_job(job_id: str, payload: QuickSourceIndexRequest) -> None:
    started_at = time.time()
    QUICK_INDEX_JOBS[job_id] = {
        "status": "running",
        "message": "Indexing source media into a grounded signal.",
        "started_at": started_at,
        "completed_at": None,
        "result": None,
        "error": None,
    }
    try:
        result = await agent.extract_signal(
            SignalExtractionRequest(
                input_text=payload.source_text,
                source_manifest=payload.source_manifest,
                normalized_source_text=payload.normalized_source_text,
                source_text_origin=payload.source_text_origin,
            )
        )
        if result.get("status") != "success":
            raise ValueError(result.get("message") or "Source indexing failed.")
        QUICK_INDEX_JOBS[job_id] = {
            "status": "completed",
            "message": "Source indexing complete.",
            "started_at": started_at,
            "completed_at": time.time(),
            "result": {
                "content_signal": result.get("content_signal", {}),
                "normalized_source_text": result.get("normalized_source_text", ""),
                "source_text_origin": result.get("source_text_origin"),
                "trace": result.get("trace", {}),
            },
            "error": None,
        }
    except Exception as exc:
        QUICK_INDEX_JOBS[job_id] = {
            "status": "failed",
            "message": "Source indexing failed.",
            "started_at": started_at,
            "completed_at": time.time(),
            "result": None,
            "error": str(exc),
        }


@router.post("/extract-signal")
async def extract_signal(payload: SignalExtractionRequest):
    return await agent.extract_signal(payload)


@router.post("/quick-source-index/start")
async def quick_source_index_start(payload: QuickSourceIndexRequest):
    if not payload.source_text.strip() and not payload.normalized_source_text.strip() and payload.source_manifest is None:
        raise HTTPException(status_code=400, detail="Provide transcript text or upload at least one source asset before indexing.")

    job_id = f"qidx-{uuid4().hex[:10]}"
    QUICK_INDEX_JOBS[job_id] = {
        "status": "queued",
        "message": "Queued for source indexing.",
        "started_at": time.time(),
        "completed_at": None,
        "result": None,
        "error": None,
    }
    asyncio.create_task(_run_quick_source_index_job(job_id, payload))
    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Quick source indexing started.",
    }


@router.get("/quick-source-index/{job_id}")
async def quick_source_index_status(job_id: str):
    job = QUICK_INDEX_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown quick source index job.")
    return job


@router.get("/generate-stream")
async def generate_stream(
    request: Request,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str = "illustration",
):
    return EventSourceResponse(
        agent.generate_stream_events(
            request=request,
            topic=topic,
            audience=audience,
            tone=tone,
            visual_mode=visual_mode,
        )
    )


@router.post("/generate-stream-advanced")
async def generate_stream_advanced(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        body = {}

    payload = AdvancedStreamRequest(
        source_text=body.get("source_text", "") if isinstance(body.get("source_text"), str) else "",
        source_manifest=body.get("source_manifest") if isinstance(body.get("source_manifest"), dict) else None,
        normalized_source_text=body.get("normalized_source_text", "") if isinstance(body.get("normalized_source_text"), str) else "",
        source_text_origin=body.get("source_text_origin") if isinstance(body.get("source_text_origin"), str) else None,
        content_signal=body.get("content_signal", {}) if isinstance(body.get("content_signal"), dict) else {},
        render_profile=body.get("render_profile", {}) if isinstance(body.get("render_profile"), dict) else {},
        script_pack=body.get("script_pack") if isinstance(body.get("script_pack"), dict) else None,
        artifact_scope=_artifact_scope_from_body(body),
    )

    return EventSourceResponse(
        agent.generate_stream_advanced_events(
            request=request,
            payload=payload,
        )
    )


@router.post("/generate-script-pack-advanced")
async def generate_script_pack_advanced(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        body = {}

    payload = ScriptPackRequest(
        source_text=body.get("source_text", "") if isinstance(body.get("source_text"), str) else "",
        source_manifest=body.get("source_manifest") if isinstance(body.get("source_manifest"), dict) else None,
        normalized_source_text=body.get("normalized_source_text", "") if isinstance(body.get("normalized_source_text"), str) else "",
        source_text_origin=body.get("source_text_origin") if isinstance(body.get("source_text_origin"), str) else None,
        content_signal=body.get("content_signal", {}) if isinstance(body.get("content_signal"), dict) else {},
        render_profile=body.get("render_profile", {}) if isinstance(body.get("render_profile"), dict) else {},
        artifact_scope=_artifact_scope_from_body(body),
    )
    return await agent.generate_script_pack_advanced(payload)


@router.post("/generate-quick-artifact")
async def generate_quick_artifact(payload: QuickArtifactRequest, request: Request):
    return await agent.generate_quick_artifact(payload, request=request)


@router.post("/generate-quick-reel")
async def generate_quick_reel(payload: QuickReelRequest):
    return await agent.generate_quick_reel(payload)


@router.post("/regenerate-quick-block")
async def regenerate_quick_block(payload: QuickBlockOverrideRequest, request: Request):
    return await agent.regenerate_quick_block(payload, request=request)


@router.post("/regenerate-quick-artifact")
async def regenerate_quick_artifact(payload: QuickArtifactOverrideRequest, request: Request):
    return await agent.regenerate_quick_artifact(payload, request=request)


@router.post("/regenerate-scene")
async def regenerate_scene(payload: RegenerateSceneRequest, request: Request):
    return await agent.regenerate_scene(payload, request)
