from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.schemas.requests import (
    AdvancedStreamRequest,
    RegenerateSceneRequest,
    ScriptPackRequest,
    SignalExtractionRequest,
)
from app.services import GeminiStoryAgent

router = APIRouter()
agent = GeminiStoryAgent()

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


@router.post("/extract-signal")
async def extract_signal(payload: SignalExtractionRequest):
    return await agent.extract_signal(payload)


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
        content_signal=body.get("content_signal", {}) if isinstance(body.get("content_signal"), dict) else {},
        render_profile=body.get("render_profile", {}) if isinstance(body.get("render_profile"), dict) else {},
        artifact_scope=_artifact_scope_from_body(body),
    )
    return await agent.generate_script_pack_advanced(payload)


@router.post("/regenerate-scene")
async def regenerate_scene(payload: RegenerateSceneRequest, request: Request):
    return await agent.regenerate_scene(payload, request)
