from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import Request

from app.schemas.events import build_sse_event
from app.schemas.requests import ScriptPackScene
from app.services.interleaved_parser import evaluate_scene_quality, extract_anchor_terms


async def stream_live_advanced_scene_with_qa(
    *,
    stream_scene_assets: Callable[..., AsyncIterator[dict[str, str]]],
    build_scene_attempt_constraints: Callable[..., list[str]],
    default_scene_qa_result: Callable[[str], dict[str, Any]],
    active_scene_continuity: Callable[[list[str], list[str]], list[str]],
    request: Request,
    scene: ScriptPackScene,
    thesis: str,
    audience_descriptor: str,
    goal: str,
    style_guide: str,
    artifact_type: str,
    must_include: list[str],
    must_avoid: list[str],
    claim_text_snippets: list[str],
    evidence_text_snippets: list[str],
    continuity_memory: list[str],
    scene_trace_payload: dict[str, Any],
    on_qa_result: Callable[[dict[str, Any]], None] | None = None,
    result_collector: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, str]]:
    scene_id = scene.scene_id
    retries_used = 0
    qa_result: dict[str, Any] = {
        **default_scene_qa_result(scene_id),
    }
    latest_scene_result: dict[str, Any] = {}
    retry_reason_constraints: list[str] = []

    for attempt_index in range(2):
        latest_scene_result = {}
        current_continuity = active_scene_continuity(
            continuity_memory,
            list(scene.continuity_refs),
        )
        attempt_constraints = build_scene_attempt_constraints(
            acceptance_checks=list(scene.acceptance_checks),
            retry_constraints=retry_reason_constraints,
        )

        if attempt_index > 0:
            yield build_sse_event(
                "scene_retry_reset",
                {
                    "scene_id": scene_id,
                    "retry_index": attempt_index,
                    "trace": scene_trace_payload,
                },
            )

        async for event in stream_scene_assets(
            request=request,
            scene_id=scene_id,
            topic=thesis,
            audience=audience_descriptor,
            tone=goal,
            scene_title=scene.title,
            narration_focus=scene.narration_focus,
            scene_goal=scene.scene_goal,
            style_guide=style_guide,
            visual_prompt=scene.visual_prompt,
            image_prefix="advanced_interleaved",
            audio_prefix="advanced_audio",
            artifact_type=artifact_type,
            scene_mode=scene.scene_mode,
            layout_template=scene.layout_template,
            focal_subject=scene.focal_subject,
            visual_hierarchy=scene.visual_hierarchy,
            modules=scene.modules,
            claim_refs=scene.claim_refs,
            claim_text_snippets=claim_text_snippets,
            evidence_text_snippets=evidence_text_snippets,
            crop_safe_regions=scene.crop_safe_regions,
            continuity_hints=current_continuity,
            extra_constraints=attempt_constraints,
            result_collector=latest_scene_result,
            trace_payload=scene_trace_payload,
        ):
            yield event

        qa_result = evaluate_scene_quality(
            scene=scene,
            generated_text=str(latest_scene_result.get("text", "")),
            image_url=str(latest_scene_result.get("image_url", "")),
            must_include=must_include,
            must_avoid=must_avoid,
            continuity_hints=current_continuity,
            attempt=attempt_index + 1,
            artifact_type=artifact_type,
        )
        if on_qa_result is not None:
            on_qa_result(qa_result)
        yield build_sse_event(
            "qa_status",
            {
                **qa_result,
                "trace": scene_trace_payload,
            },
        )

        if qa_result["status"] != "FAIL":
            break

        if attempt_index == 0:
            retry_reason_constraints = list(qa_result["reasons"])
            retries_used = 1
            yield build_sse_event(
                "qa_retry",
                {
                    "scene_id": scene_id,
                    "retry_index": 1,
                    "reasons": qa_result["reasons"],
                    "trace": scene_trace_payload,
                },
            )

    continuity_tokens = tuple(extract_anchor_terms(str(latest_scene_result.get("text", "")), limit=4))
    if result_collector is not None:
        result_collector.update(
            {
                "qa_result": qa_result,
                "retries_used": retries_used,
                "word_count": int(latest_scene_result.get("word_count", 0)),
                "continuity_tokens": continuity_tokens,
            }
        )

    yield build_sse_event(
        "scene_done",
        {
            "scene_id": scene_id,
            "qa_status": qa_result["status"],
            "auto_retries": retries_used,
            "trace": scene_trace_payload,
        },
    )
