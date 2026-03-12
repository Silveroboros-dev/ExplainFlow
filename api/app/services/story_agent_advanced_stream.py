from dataclasses import dataclass
from typing import Any

from app.schemas.requests import ScriptPack, ScriptPackScene


@dataclass(frozen=True)
class PreparedAdvancedSceneSpec:
    scene: ScriptPackScene
    scene_id: str
    title: str
    scene_trace_id: str
    scene_trace_payload: dict[str, Any]
    claim_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    claim_text_snippets: tuple[str, ...]
    evidence_text_snippets: tuple[str, ...]


def build_advanced_scene_queue_payloads(script_pack: ScriptPack) -> list[dict[str, Any]]:
    return [
        {
            "scene_id": scene.scene_id,
            "title": scene.title,
            "claim_refs": scene.claim_refs,
            "evidence_refs": scene.evidence_refs,
            "render_strategy": scene.render_strategy,
            "source_media_count": len(scene.source_media),
            "narration_focus": scene.narration_focus,
        }
        for scene in script_pack.scenes
    ]


def prepare_advanced_scene_spec(
    *,
    scene: ScriptPackScene,
    scene_id: str,
    title: str,
    scene_trace_id: str,
    scene_trace_payload: dict[str, Any],
    claim_refs: list[str],
    evidence_refs: list[str],
    claim_text_snippets: list[str],
    evidence_text_snippets: list[str],
) -> PreparedAdvancedSceneSpec:
    return PreparedAdvancedSceneSpec(
        scene=scene,
        scene_id=scene_id,
        title=title,
        scene_trace_id=scene_trace_id,
        scene_trace_payload=scene_trace_payload,
        claim_refs=tuple(claim_refs),
        evidence_refs=tuple(evidence_refs),
        claim_text_snippets=tuple(claim_text_snippets),
        evidence_text_snippets=tuple(evidence_text_snippets),
    )


def build_scene_start_payload(
    *,
    spec: PreparedAdvancedSceneSpec,
    source_media: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "scene_id": spec.scene_id,
        "title": spec.title,
        "claim_refs": list(spec.claim_refs),
        "evidence_refs": list(spec.evidence_refs),
        "render_strategy": spec.scene.render_strategy,
        "source_media": source_media,
        "trace": dict(spec.scene_trace_payload),
    }


def default_scene_qa_result(scene_id: str) -> dict[str, Any]:
    return {
        "scene_id": scene_id,
        "status": "WARN",
        "score": 0.0,
        "reasons": ["Quality checks not executed."],
        "attempt": 1,
        "word_count": 0,
    }


def build_scene_attempt_constraints(
    *,
    acceptance_checks: list[str],
    override_constraints: list[str] | None = None,
    retry_constraints: list[str] | None = None,
) -> list[str]:
    constraints = list(acceptance_checks)
    constraints.extend(
        constraint.strip()
        for constraint in (override_constraints or [])
        if isinstance(constraint, str) and constraint.strip()
    )
    if retry_constraints:
        constraints.append(
            f"Fix these QA issues from previous attempt: {'; '.join(retry_constraints[:3])}."
        )
    return constraints


def active_scene_continuity(
    continuity_memory: list[str],
    scene_continuity_refs: list[str],
) -> list[str]:
    return (continuity_memory[-3:] + list(scene_continuity_refs))[-6:]


def update_scene_continuity_memory(
    continuity_memory: list[str],
    *,
    title: str,
    continuity_tokens: list[str] | tuple[str, ...],
) -> list[str]:
    if not continuity_tokens:
        return continuity_memory[-8:]
    return (continuity_memory + [f"{title}: {', '.join(continuity_tokens)}"])[-8:]
