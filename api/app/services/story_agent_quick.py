from typing import Any

from app.schemas.requests import ScenePlanSchema
from app.services.interleaved_parser import normalized_scene_id
from app.services.story_agent_source_media import evidence_summary_bits


def quick_grounded_claim_cards(
    content_signal: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    signal = content_signal or {}
    claim_cards: list[dict[str, Any]] = []
    for claim in signal.get("key_claims", [])[:6]:
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id", "")).strip()
        claim_text = str(claim.get("claim_text", "")).strip()
        if not claim_id or not claim_text:
            continue
        evidence_summary = "; ".join(
            evidence_summary_bits(claim.get("evidence_snippets", []))
        )
        claim_cards.append(
            {
                "claim_id": claim_id,
                "claim_text": claim_text,
                "evidence_summary": evidence_summary,
            }
        )
    return claim_cards


def build_quick_stream_planning_prompt(
    *,
    topic: str,
    audience: str,
    tone: str,
    style_guide: str,
) -> str:
    return (
        f"Create a 4-scene outline for a visual explainer about '{topic}'. "
        f"Target audience: {audience}. Tone: {tone or 'clear and engaging'}. "
        "You MUST generate EXACTLY 4 scenes.\n\n"
        f"Visual rule: {style_guide}"
    )


def normalize_quick_stream_scenes(
    *,
    parsed_scenes: list[ScenePlanSchema],
    topic: str,
) -> list[ScenePlanSchema]:
    scenes = list(parsed_scenes[:4])
    while len(scenes) < 4:
        idx = len(scenes) + 1
        scenes.append(
            ScenePlanSchema(
                scene_id=f"scene-{idx}",
                title=f"Scene {idx}",
                narration_focus=f"Explain key point {idx} about {topic}.",
                visual_prompt="Generate a visually rich educational image for this scene.",
            )
        )
    return scenes


def normalize_quick_scene_identity(
    *,
    scene: ScenePlanSchema,
    index: int,
) -> tuple[str, str, str, str, list[str]]:
    scene_id = normalized_scene_id(scene.scene_id, index)
    title = scene.title or f"Scene {index}"
    narration_focus = scene.narration_focus or f"Explain key point {index}."
    visual_prompt = scene.visual_prompt or ""
    claim_refs = [ref for ref in scene.claim_refs if ref]
    return scene_id, title, narration_focus, visual_prompt, claim_refs


def build_quick_scene_start_payload(
    *,
    scene_id: str,
    title: str,
    claim_refs: list[str],
    scene_trace_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "scene_id": scene_id,
        "title": title,
        "claim_refs": claim_refs,
        "trace": scene_trace_payload,
    }
