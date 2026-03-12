from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.schemas.events import build_sse_event
from app.schemas.requests import ScriptPack, ScriptPackScene
from app.services.interleaved_parser import evaluate_scene_quality
from app.services.story_agent_buffered_scene import (
    BufferedScenePassResult,
    execute_buffered_scene_pass,
)


@dataclass(frozen=True)
class AdvancedSceneQaLoopResult:
    events: tuple[dict[str, str], ...]
    qa_result: dict[str, Any]
    retries_used: int
    latest_pass: BufferedScenePassResult | None


async def execute_advanced_scene_qa_loop(
    *,
    stream_scene_assets: Any,
    build_scene_attempt_constraints: Any,
    default_scene_qa_result: Any,
    request: Request,
    scene: ScriptPackScene,
    thesis: str,
    audience_descriptor: str,
    goal: str,
    style_guide: str,
    script_pack: ScriptPack,
    must_include: list[str],
    must_avoid: list[str],
    claim_text_snippets: list[str],
    evidence_text_snippets: list[str],
    active_continuity: list[str],
    scene_trace_payload: dict[str, Any],
    retry_reason_constraints: list[str] | None = None,
    extra_constraints: list[str] | None = None,
) -> AdvancedSceneQaLoopResult:
    scene_id = scene.scene_id
    events: list[dict[str, str]] = []
    retries_used = 0
    qa_result: dict[str, Any] = {
        **default_scene_qa_result(scene_id),
    }
    latest_pass: BufferedScenePassResult | None = None
    retry_constraints = list(retry_reason_constraints or [])
    override_constraints = list(extra_constraints or [])

    for attempt_index in range(2):
        attempt_constraints = build_scene_attempt_constraints(
            acceptance_checks=list(scene.acceptance_checks),
            override_constraints=override_constraints,
            retry_constraints=retry_constraints,
        )

        prelude_events: list[dict[str, str]] = []
        if attempt_index > 0:
            prelude_events.append(
                build_sse_event(
                    "scene_retry_reset",
                    {
                        "scene_id": scene_id,
                        "retry_index": attempt_index,
                        "trace": scene_trace_payload,
                    },
                )
            )

        latest_pass = await execute_buffered_scene_pass(
            stream_scene_assets=stream_scene_assets,
            request=request,
            prelude_events=prelude_events,
            stream_kwargs={
                "scene_id": scene_id,
                "topic": thesis,
                "audience": audience_descriptor,
                "tone": goal,
                "scene_title": scene.title,
                "narration_focus": scene.narration_focus,
                "scene_goal": scene.scene_goal,
                "style_guide": style_guide,
                "visual_prompt": scene.visual_prompt,
                "image_prefix": "advanced_interleaved",
                "audio_prefix": "advanced_audio",
                "artifact_type": script_pack.artifact_type,
                "scene_mode": scene.scene_mode,
                "layout_template": scene.layout_template,
                "focal_subject": scene.focal_subject,
                "visual_hierarchy": scene.visual_hierarchy,
                "modules": scene.modules,
                "claim_refs": scene.claim_refs,
                "claim_text_snippets": claim_text_snippets,
                "evidence_text_snippets": evidence_text_snippets,
                "crop_safe_regions": scene.crop_safe_regions,
                "continuity_hints": active_continuity,
                "extra_constraints": attempt_constraints,
                "trace_payload": scene_trace_payload,
            },
        )
        events.extend(latest_pass.events)

        qa_result = evaluate_scene_quality(
            scene=scene,
            generated_text=latest_pass.text,
            image_url=latest_pass.image_url,
            must_include=must_include,
            must_avoid=must_avoid,
            continuity_hints=active_continuity,
            attempt=attempt_index + 1,
            artifact_type=script_pack.artifact_type,
        )
        events.append(
            build_sse_event(
                "qa_status",
                {
                    **qa_result,
                    "trace": scene_trace_payload,
                },
            )
        )

        if qa_result["status"] != "FAIL":
            break

        if attempt_index == 0:
            retry_constraints = list(qa_result["reasons"])
            retries_used = 1
            events.append(
                build_sse_event(
                    "qa_retry",
                    {
                        "scene_id": scene_id,
                        "retry_index": 1,
                        "reasons": qa_result["reasons"],
                        "trace": scene_trace_payload,
                    },
                )
            )

    return AdvancedSceneQaLoopResult(
        events=tuple(events),
        qa_result=qa_result,
        retries_used=retries_used,
        latest_pass=latest_pass,
    )
