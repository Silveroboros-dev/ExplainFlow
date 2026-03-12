from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import Request
from google.genai import types

from app.schemas.events import (
    add_checkpoint,
    add_or_update_scene_trace,
    build_checkpoint_event,
    build_sse_event,
    init_trace_envelope,
    trace_meta,
)
from app.schemas.requests import (
    OutlineSchema,
    QuickArtifactBlockSchema,
    QuickArtifactOverrideRequest,
    QuickArtifactRequest,
    QuickArtifactSchema,
    QuickBlockOverrideRequest,
    QuickReelRequest,
    QuickVideoRequest,
)


@dataclass(frozen=True)
class QuickRequestContext:
    topic: str
    audience: str
    tone: str
    visual_mode: str


def resolve_quick_request_context(
    *,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
) -> QuickRequestContext:
    return QuickRequestContext(
        topic=topic.strip(),
        audience=audience.strip() or "general audience",
        tone=tone.strip(),
        visual_mode=visual_mode.strip() or "illustration",
    )


async def generate_quick_artifact_response(
    agent: Any,
    *,
    payload: QuickArtifactRequest,
    request: Request,
) -> dict[str, Any]:
    ctx = resolve_quick_request_context(
        topic=payload.topic,
        audience=payload.audience,
        tone=payload.tone,
        visual_mode=payload.visual_mode,
    )
    if not ctx.topic:
        return {"status": "error", "message": "Provide a topic before generating a quick artifact."}

    style_guide = agent._style_guide_for_mode(ctx.visual_mode)
    content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
    source_excerpt = (payload.normalized_source_text or payload.source_text or "").strip()[:3200]
    prompt = agent._build_quick_artifact_prompt(
        topic=ctx.topic,
        audience=ctx.audience,
        tone=ctx.tone,
        visual_mode=ctx.visual_mode,
        style_guide=style_guide,
        content_signal=content_signal,
        source_excerpt=source_excerpt,
    )

    try:
        response = await agent.client.aio.models.generate_content(
            model=agent._quick_artifact_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                response_mime_type="application/json",
                response_schema=QuickArtifactSchema,
            ),
        )
        artifact = QuickArtifactSchema.model_validate_json(response.text)
    except Exception:
        artifact = agent._fallback_quick_artifact(
            topic=ctx.topic,
            audience=ctx.audience,
            tone=ctx.tone,
            visual_mode=ctx.visual_mode,
            content_signal=content_signal,
        )

    normalized = agent._normalize_quick_artifact(
        artifact,
        topic=ctx.topic,
        audience=ctx.audience,
        tone=ctx.tone,
        visual_mode=ctx.visual_mode,
        content_signal=content_signal,
    )
    normalized = agent._enrich_quick_artifact_with_source_media(
        artifact=normalized,
        content_signal=content_signal,
        source_manifest=payload.source_manifest,
    )
    normalized = await agent._populate_quick_block_visuals(
        request=request,
        topic=ctx.topic,
        audience=ctx.audience,
        tone=ctx.tone,
        visual_mode=ctx.visual_mode,
        artifact=normalized,
        content_signal=content_signal,
    )
    try:
        hero_image_url = await agent._generate_quick_hero_image(
            request=request,
            topic=ctx.topic,
            audience=ctx.audience,
            tone=ctx.tone,
            visual_mode=ctx.visual_mode,
            artifact=normalized,
            content_signal=content_signal,
        )
    except Exception:
        hero_image_url = ""
    if hero_image_url:
        normalized = normalized.model_copy(update={"hero_image_url": hero_image_url})
    return {"status": "success", "artifact": normalized.model_dump()}


async def generate_quick_reel_response(
    agent: Any,
    *,
    payload: QuickReelRequest,
) -> dict[str, Any]:
    artifact = QuickArtifactSchema.model_validate(payload.artifact)
    if not artifact.blocks:
        return {"status": "error", "message": "Provide a quick artifact before generating a proof reel."}

    content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
    reel = agent._build_quick_reel_from_artifact(
        artifact=artifact,
        content_signal=content_signal,
        source_manifest=payload.source_manifest,
    )
    return {
        "status": "success",
        "artifact": artifact.model_copy(update={"reel": reel}).model_dump(),
    }


async def generate_quick_video_response(
    agent: Any,
    *,
    payload: QuickVideoRequest,
    request: Request,
) -> dict[str, Any]:
    artifact = QuickArtifactSchema.model_validate(payload.artifact)
    if not artifact.blocks:
        return {"status": "error", "message": "Provide a quick artifact before generating a video."}

    content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
    working_artifact = artifact
    if working_artifact.reel is None or not working_artifact.reel.segments:
        reel = agent._build_quick_reel_from_artifact(
            artifact=working_artifact,
            content_signal=content_signal,
            source_manifest=payload.source_manifest,
        )
        working_artifact = working_artifact.model_copy(update={"reel": reel})

    try:
        video = await agent._build_quick_video_async(
            request=request,
            artifact=working_artifact,
            source_manifest=payload.source_manifest,
        )
    except Exception as exc:
        return {"status": "error", "message": str(exc) or "Quick MP4 generation failed."}

    return {
        "status": "success",
        "artifact": working_artifact.model_copy(update={"video": video}).model_dump(),
    }


async def regenerate_quick_block_response(
    agent: Any,
    *,
    payload: QuickBlockOverrideRequest,
    request: Request,
) -> dict[str, Any]:
    ctx = resolve_quick_request_context(
        topic=payload.topic,
        audience=payload.audience,
        tone=payload.tone,
        visual_mode=payload.visual_mode,
    )
    instruction = payload.instruction.strip()
    if not ctx.topic or not instruction:
        return {"status": "error", "message": "Provide a topic and a direction note before regenerating a block."}

    artifact = QuickArtifactSchema.model_validate(payload.artifact)
    target_block = next((block for block in artifact.blocks if block.block_id == payload.block_id), None)
    if target_block is None:
        return {"status": "error", "message": f"Unknown block id: {payload.block_id}"}
    content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
    prompt = agent._build_quick_block_override_prompt(
        topic=ctx.topic,
        audience=ctx.audience,
        tone=ctx.tone,
        visual_mode=ctx.visual_mode,
        artifact=artifact,
        target_block=target_block,
        instruction=instruction,
        content_signal=content_signal,
    )

    try:
        response = await agent.client.aio.models.generate_content(
            model=agent._quick_artifact_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                response_mime_type="application/json",
                response_schema=QuickArtifactBlockSchema,
            ),
        )
        updated_block = QuickArtifactBlockSchema.model_validate_json(response.text)
    except Exception as exc:
        return {"status": "error", "message": f"Block override failed: {exc}"}

    normalized_block = agent._normalize_quick_override_block(
        target_block=target_block,
        updated_block=updated_block,
    )
    force_visual_refresh = agent._quick_override_requests_visual_refresh(
        instruction=instruction,
        original_block=target_block,
        updated_block=normalized_block,
    )
    visualized_block = agent._enrich_quick_artifact_with_source_media(
        artifact=QuickArtifactSchema(
            artifact_id=artifact.artifact_id,
            title=artifact.title,
            subtitle=artifact.subtitle,
            summary=artifact.summary,
            visual_style=artifact.visual_style,
            hero_direction=artifact.hero_direction,
            blocks=[normalized_block],
        ),
        content_signal=content_signal,
        source_manifest=payload.source_manifest,
    )
    visualized_block = await agent._populate_quick_block_visuals(
        request=request,
        topic=ctx.topic,
        audience=ctx.audience,
        tone=ctx.tone,
        visual_mode=ctx.visual_mode,
        artifact=visualized_block,
        content_signal=content_signal,
        force_block_ids={target_block.block_id} if force_visual_refresh else None,
    )
    return {"status": "success", "block": visualized_block.blocks[0].model_dump()}


async def regenerate_quick_artifact_response(
    agent: Any,
    *,
    payload: QuickArtifactOverrideRequest,
    request: Request,
) -> dict[str, Any]:
    ctx = resolve_quick_request_context(
        topic=payload.topic,
        audience=payload.audience,
        tone=payload.tone,
        visual_mode=payload.visual_mode,
    )
    instruction = payload.instruction.strip()
    if not ctx.topic or not instruction:
        return {"status": "error", "message": "Provide a topic and a direction note before regenerating the quick artifact."}

    artifact = QuickArtifactSchema.model_validate(payload.artifact)
    content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
    anchor_block_id = (payload.anchor_block_id or "").strip() or None
    anchor_index = next(
        (idx for idx, block in enumerate(artifact.blocks) if block.block_id == anchor_block_id),
        0 if anchor_block_id is None else -1,
    )
    if anchor_index < 0:
        return {"status": "error", "message": f"Unknown anchor block id: {anchor_block_id}"}

    prompt = agent._build_quick_artifact_override_prompt(
        topic=ctx.topic,
        audience=ctx.audience,
        tone=ctx.tone,
        visual_mode=ctx.visual_mode,
        artifact=artifact,
        instruction=instruction,
        content_signal=content_signal,
        anchor_block_id=anchor_block_id,
        anchor_index=anchor_index,
    )

    try:
        response = await agent.client.aio.models.generate_content(
            model=agent._quick_artifact_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                response_mime_type="application/json",
                response_schema=QuickArtifactSchema,
            ),
        )
        updated_artifact = QuickArtifactSchema.model_validate_json(response.text)
    except Exception as exc:
        return {"status": "error", "message": f"Global override failed: {exc}"}

    normalized = agent._normalize_quick_artifact(
        updated_artifact,
        topic=ctx.topic,
        audience=ctx.audience,
        tone=ctx.tone,
        visual_mode=ctx.visual_mode,
        content_signal=content_signal,
    )
    normalized = agent._merge_regenerated_quick_artifact(
        original_artifact=artifact,
        normalized_artifact=normalized,
        anchor_index=anchor_index,
    )
    normalized = agent._enrich_quick_artifact_with_source_media(
        artifact=normalized,
        content_signal=content_signal,
        source_manifest=payload.source_manifest,
    )
    normalized = await agent._populate_quick_block_visuals(
        request=request,
        topic=ctx.topic,
        audience=ctx.audience,
        tone=ctx.tone,
        visual_mode=ctx.visual_mode,
        artifact=normalized,
        content_signal=content_signal,
        only_block_ids={block.block_id for block in normalized.blocks[anchor_index:]} if anchor_index > 0 else None,
    )
    try:
        hero_image_url = await agent._generate_quick_hero_image(
            request=request,
            topic=ctx.topic,
            audience=ctx.audience,
            tone=ctx.tone,
            visual_mode=ctx.visual_mode,
            artifact=normalized,
            content_signal=content_signal,
        )
    except Exception:
        hero_image_url = artifact.hero_image_url or ""
    if hero_image_url:
        normalized = normalized.model_copy(update={"hero_image_url": hero_image_url})
    elif artifact.hero_image_url:
        normalized = normalized.model_copy(update={"hero_image_url": artifact.hero_image_url})
    return {"status": "success", "artifact": normalized.model_dump()}


async def generate_quick_stream_events(
    agent: Any,
    *,
    request: Request,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str = "illustration",
) -> AsyncIterator[dict[str, str]]:
    run_id = agent._new_run_id("interleaved-run")
    artifact_scope = agent._resolve_artifact_scope(
        requested_scope=None,
        render_profile=None,
        default_scope=["story_cards", "voiceover"],
    )
    trace = init_trace_envelope(
        trace_id=f"trace-{uuid4().hex[:12]}",
        run_id=run_id,
        flow="quick_stream",
        artifact_scope=artifact_scope,
    )

    style_guide = agent._style_guide_for_mode(visual_mode)
    planning_prompt = agent._build_quick_stream_planning_prompt(
        topic=topic,
        audience=audience,
        tone=tone,
        style_guide=style_guide,
    )

    cp2 = add_checkpoint(
        trace,
        checkpoint="CP2_ARTIFACTS_LOCKED",
        status="passed",
        details={"artifact_scope": artifact_scope, "source": "quick_defaults"},
    )
    yield build_checkpoint_event(trace, cp2)

    cp3 = add_checkpoint(
        trace,
        checkpoint="CP3_RENDER_LOCKED",
        status="passed",
        details={"visual_mode": visual_mode},
    )
    yield build_checkpoint_event(trace, cp3)

    try:
        plan_response = await agent.client.aio.models.generate_content(
            model=agent._signal_structural_model(),
            contents=planning_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
                response_schema=OutlineSchema,
            ),
        )
        parsed_outline = OutlineSchema.model_validate_json(plan_response.text)
        planned_scene_count = len(parsed_outline.scenes[:4])
        scenes = agent._normalize_quick_stream_scenes(
            parsed_scenes=parsed_outline.scenes,
            topic=topic,
        )

        cp1 = add_checkpoint(
            trace,
            checkpoint="CP1_SIGNAL_READY",
            status="passed",
            details={"source": "quick_prompt_planning", "planned_scenes": planned_scene_count},
        )
        yield build_checkpoint_event(trace, cp1)

        yield build_sse_event(
            "scene_queue_ready",
            {
                "scenes": [scene.model_dump() for scene in scenes],
                "optimized_count": len(scenes),
                "trace": trace_meta(trace, checkpoint="CP4_SCRIPT_LOCKED"),
            },
        )

        cp4 = add_checkpoint(
            trace,
            checkpoint="CP4_SCRIPT_LOCKED",
            status="passed",
            details={"scene_count": len(scenes), "mode": "quick_auto_outline"},
        )
        yield build_checkpoint_event(trace, cp4)

        scene_claim_map: dict[str, list[str]] = {}
        for idx, scene in enumerate(scenes, start=1):
            if await request.is_disconnected():
                return

            scene_id, title, narration_focus, visual_prompt, claim_refs = (
                agent._normalize_quick_scene_identity(scene=scene, index=idx)
            )
            scene_trace_id = f"{trace.trace_id}-{scene_id}-{uuid4().hex[:8]}"
            scene_claim_map[scene_id] = claim_refs
            add_or_update_scene_trace(
                trace,
                scene_id=scene_id,
                scene_trace_id=scene_trace_id,
                claim_refs=claim_refs,
            )
            scene_trace_payload = trace_meta(trace, scene_trace_id=scene_trace_id)

            yield build_sse_event(
                "scene_start",
                agent._build_quick_scene_start_payload(
                    scene_id=scene_id,
                    title=title,
                    claim_refs=claim_refs,
                    scene_trace_payload=scene_trace_payload,
                ),
            )

            scene_result: dict[str, Any] = {}

            async for event in agent._stream_scene_assets(
                request=request,
                scene_id=scene_id,
                topic=topic,
                audience=audience,
                tone=tone,
                scene_title=title,
                narration_focus=narration_focus,
                style_guide=style_guide,
                visual_prompt=visual_prompt,
                image_prefix="interleaved",
                audio_prefix="audio",
                result_collector=scene_result,
                trace_payload=scene_trace_payload,
            ):
                yield event

            add_or_update_scene_trace(
                trace,
                scene_id=scene_id,
                scene_trace_id=scene_trace_id,
                word_count=int(scene_result.get("word_count", 0)),
            )
            yield build_sse_event(
                "scene_done",
                {"scene_id": scene_id, "trace": scene_trace_payload},
            )

        cp5 = add_checkpoint(
            trace,
            checkpoint="CP5_STREAM_COMPLETE",
            status="passed",
            details={"scene_count": len(scenes)},
        )
        yield build_checkpoint_event(trace, cp5)

        traceability = agent._claim_traceability_summary(
            claim_ids=[],
            scene_claim_map=scene_claim_map,
        )

        cp6 = add_checkpoint(
            trace,
            checkpoint="CP6_BUNDLE_FINALIZED",
            status="passed",
            details={"bundle_url": f"/api/final-bundle/{run_id}"},
        )
        yield build_checkpoint_event(trace, cp6)

        yield build_sse_event(
            "final_bundle_ready",
            {
                "run_id": run_id,
                "bundle_url": f"/api/final-bundle/{run_id}",
                "trace": trace.model_dump(),
                "claim_traceability": traceability,
            },
        )
    except Exception as exc:
        print(f"Error generating stream: {exc}")
        cp1_passed = any(
            checkpoint.checkpoint == "CP1_SIGNAL_READY" and checkpoint.status == "passed"
            for checkpoint in trace.checkpoints
        )
        failed_checkpoint = "CP5_STREAM_COMPLETE" if cp1_passed else "CP1_SIGNAL_READY"
        failed_record = add_checkpoint(
            trace,
            checkpoint=failed_checkpoint,
            status="failed",
            details={"error": str(exc)},
        )
        yield build_checkpoint_event(trace, failed_record)
        message = agent._friendly_quota_error_message() if agent._is_resource_exhausted(exc) else str(exc)
        yield build_sse_event("error", {"error": message, "trace": trace.model_dump()})
