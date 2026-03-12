import re
from dataclasses import dataclass
from typing import Any

from app.schemas.requests import SceneModuleSchema, WorkflowSceneContextRequest
from app.services.interleaved_parser import extract_anchor_terms, scene_narration_word_budget
from app.services.story_agent_source_media import evidence_summary_bits


@dataclass(frozen=True)
class RenderProfileSceneContext:
    visual_mode: str
    audience_level: str
    audience_persona: str
    domain_context: str
    audience_descriptor: str
    taste_bar: str
    must_include: tuple[str, ...]
    must_avoid: tuple[str, ...]
    goal: str
    style_guide: str


def style_guide_for_mode(visual_mode: str) -> str:
    if visual_mode == "diagram":
        return (
            "Visuals must be clean, high-detail educational diagrams or "
            "historically/scientifically accurate realistic landscapes. Ensure the visual "
            "specifically illustrates the scientific or historical concepts mentioned in "
            "the text. Avoid image text labels. Prefer extreme accuracy, realism, and clarity."
        )
    if visual_mode == "hybrid":
        return (
            "Visuals must blend 3D subjects with holographic UI overlays, charts, "
            "or interface elements in a consistent style."
        )
    return (
        "Visuals must be high-quality cinematic 3D renders or polished vector-style "
        "illustrations with consistent palette and character design."
    )


def build_render_profile_scene_context(
    render_profile: dict[str, Any],
) -> RenderProfileSceneContext:
    visual_mode = str(render_profile.get("visual_mode", "illustration"))
    audience_cfg = render_profile.get("audience", {})
    audience_level = str(audience_cfg.get("level", "beginner")).lower()
    audience_persona = str(audience_cfg.get("persona", "General audience")).strip()
    domain_context = str(audience_cfg.get("domain_context", "")).strip()
    taste_bar = str(audience_cfg.get("taste_bar", "standard")).lower()
    must_include = tuple(
        str(item).strip()
        for item in audience_cfg.get("must_include", [])
        if isinstance(item, str) and str(item).strip()
    )[:8]
    must_avoid = tuple(
        str(item).strip()
        for item in audience_cfg.get("must_avoid", [])
        if isinstance(item, str) and str(item).strip()
    )[:8]
    goal = str(render_profile.get("goal", "teach"))
    style_descriptors = ", ".join(render_profile.get("style", {}).get("descriptors", ["clean", "modern"]))
    palette = render_profile.get("palette", {})

    style_guide = f"Visual Mode: {visual_mode.upper()}.\n"
    style_guide += f"Style Descriptors: {style_descriptors}.\n"
    style_guide += f"Taste Bar: {taste_bar.upper()}.\n"
    if palette.get("mode") == "brand":
        style_guide += (
            "Mandatory Color Palette: "
            f"Primary {palette.get('primary', '#000000')}, "
            f"Secondary {palette.get('secondary', '#FFFFFF')}, "
            f"Accent {palette.get('accent', '#FF0000')}. "
            "Use these specific hex colors prominently.\n"
        )
    else:
        style_guide += "Palette: Auto-select an engaging, educational color palette.\n"

    if visual_mode == "diagram":
        style_guide += (
            "CRITICAL: Do NOT request 2D maps with text labels. "
            "Focus on abstract or photorealistic educational infographics."
        )
    elif visual_mode == "hybrid":
        style_guide += "CRITICAL: Blend 3D objects with floating holographic UI elements or charts."

    audience_descriptor = f"{audience_persona} ({audience_level})"
    if domain_context:
        audience_descriptor += f" in {domain_context}"

    return RenderProfileSceneContext(
        visual_mode=visual_mode,
        audience_level=audience_level,
        audience_persona=audience_persona,
        domain_context=domain_context,
        audience_descriptor=audience_descriptor,
        taste_bar=taste_bar,
        must_include=must_include,
        must_avoid=must_avoid,
        goal=goal,
        style_guide=style_guide,
    )


def build_claim_grounding_maps(
    content_signal: dict[str, Any],
) -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    claim_ids = [
        str(claim.get("claim_id")).strip()
        for claim in content_signal.get("key_claims", [])
        if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
    ]
    claim_text_lookup = {
        str(claim.get("claim_id")).strip(): str(
            claim.get("claim_text") or claim.get("content") or ""
        ).strip()
        for claim in content_signal.get("key_claims", [])
        if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
    }
    claim_evidence_lookup = {
        str(claim.get("claim_id")).strip(): evidence_summary_bits(
            claim.get("evidence_snippets", [])
            if isinstance(claim.get("evidence_snippets"), list)
            else []
        )
        for claim in content_signal.get("key_claims", [])
        if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
    }
    return claim_ids, claim_text_lookup, claim_evidence_lookup


def build_scene_grounding_snippets(
    *,
    claim_refs: list[str],
    claim_text_lookup: dict[str, str],
    claim_evidence_lookup: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    claim_text_snippets = [
        claim_text_lookup[claim_ref]
        for claim_ref in claim_refs
        if claim_ref in claim_text_lookup and claim_text_lookup[claim_ref]
    ]
    evidence_text_snippets: list[str] = []
    seen_evidence_bits: set[str] = set()
    for claim_ref in claim_refs:
        for evidence_bit in claim_evidence_lookup.get(claim_ref, [])[:2]:
            if evidence_bit and evidence_bit not in seen_evidence_bits:
                evidence_text_snippets.append(evidence_bit)
                seen_evidence_bits.add(evidence_bit)
    return claim_text_snippets, evidence_text_snippets


def build_stream_scene_prompt(
    *,
    topic: str,
    audience: str,
    tone: str,
    scene_title: str,
    narration_focus: str,
    style_guide: str,
    visual_prompt: str,
    scene_goal: str = "",
    artifact_type: str = "",
    scene_mode: str = "sequential",
    layout_template: str | None = None,
    focal_subject: str | None = None,
    visual_hierarchy: list[str] | None = None,
    modules: list[SceneModuleSchema] | None = None,
    claim_refs: list[str] | None = None,
    claim_text_snippets: list[str] | None = None,
    evidence_text_snippets: list[str] | None = None,
    crop_safe_regions: list[str] | None = None,
    continuity_hints: list[str] | None = None,
    extra_constraints: list[str] | None = None,
) -> str:
    continuity_block = ""
    if continuity_hints:
        continuity_lines = "\n".join(f"- {hint}" for hint in continuity_hints[-4:])
        continuity_block = f"CONTINUITY MEMORY:\n{continuity_lines}\n\n"

    constraints_block = ""
    if extra_constraints:
        constraints_lines = "\n".join(f"- {constraint}" for constraint in extra_constraints[:8])
        constraints_block = f"ACCEPTANCE CHECKS:\n{constraints_lines}\n\n"

    hierarchy_block = ""
    if visual_hierarchy:
        hierarchy_block = "VISUAL HIERARCHY:\n" + "\n".join(
            f"- {item}" for item in visual_hierarchy[:6] if str(item).strip()
        ) + "\n\n"

    module_lines: list[str] = []
    if modules:
        for module in modules[:8]:
            module_claims = ", ".join(module.claim_refs[:4])
            line = f"- {module.label}: {module.purpose} ({module.content_type})"
            if module.placement_hint:
                line += f" | placement: {module.placement_hint}"
            if module_claims:
                line += f" | claim_refs: {module_claims}"
            module_lines.append(line)
    modules_block = f"MODULES:\n{chr(10).join(module_lines)}\n\n" if module_lines else ""

    claim_refs_block = ""
    if claim_refs:
        claim_refs_block = f"CLAIM REFS: {', '.join(ref for ref in claim_refs[:8] if ref)}\n"

    claim_text_block = ""
    if claim_text_snippets:
        claim_text_block = "SOURCE CLAIMS:\n" + "\n".join(
            f"- {snippet}" for snippet in claim_text_snippets[:6] if str(snippet).strip()
        ) + "\n\n"

    evidence_text_block = ""
    if evidence_text_snippets:
        evidence_text_block = "SOURCE EVIDENCE:\n" + "\n".join(
            f"- {snippet}" for snippet in evidence_text_snippets[:6] if str(snippet).strip()
        ) + "\n\n"

    crop_safe_block = ""
    if crop_safe_regions:
        crop_safe_block = "CROP SAFE REGIONS:\n" + "\n".join(
            f"- {item}" for item in crop_safe_regions[:4] if str(item).strip()
        ) + "\n\n"

    min_words, max_words = scene_narration_word_budget(
        scene_mode=scene_mode,
        layout_template=layout_template,
        artifact_type=artifact_type,
    )
    if artifact_type == "comparison_one_pager":
        return (
            f"CONTEXT: We are building a one-pager about '{topic}' for a {audience} audience.\n"
            f"TONE: {tone}\n"
            f"SCENE MODE: {scene_mode}\n"
            f"SCENE TITLE: {scene_title}\n"
            f"SCENE GOAL: {scene_goal}\n"
            f"READING PATH / TAKEAWAY: {narration_focus}\n"
            f"LAYOUT TEMPLATE: {layout_template or 'modular_poster'}\n"
            f"FOCAL SUBJECT: {focal_subject or topic}\n"
            f"{claim_refs_block}"
            f"{claim_text_block}"
            f"VISUAL STYLE: {style_guide}\n"
            f"VISUAL DIRECTION: {visual_prompt}\n\n"
            f"{hierarchy_block}"
            f"{modules_block}"
            f"{continuity_block}"
            f"{constraints_block}"
            "ARTIFACT RULE: This output is a single static one-pager board, not a storyboard frame and not a cinematic beat.\n"
            "BOARD RULES:\n"
            "1) Compose one poster-style canvas with clear modular zones.\n"
            "2) Create one strong entry point, structured secondary modules, and a clear synthesis area.\n"
            "3) Favor panels, dividers, icons, charts, diagrams, arrows, and grouped visual motifs over scenic imagery.\n"
            "4) Keep any implied labels minimal and legible; do not rely on dense tiny text inside the image.\n"
            "5) The text should explain how to read the board and land the core takeaway, not describe a time sequence.\n"
            "6) The image must feel publish-ready, information-dense, and editorial.\n\n"
            "TASK: Generate the content for THIS ONE-PAGER ONLY.\n"
            "STRICT OUTPUT RULES:\n"
            "1) Start immediately with the spoken support copy. NO labels like 'Narration:', NO scene numbers, NO markdown titles.\n"
            f"2) The text must be {min_words}-{max_words} words.\n"
            "3) The text must explain how to read the board and the main takeaway.\n"
            "4) Immediately after the text, generate the corresponding high-quality inline image.\n"
            "5) The image MUST be a single composed one-pager canvas that matches the visual direction.\n"
            "6) DO NOT output any other text or conversational filler."
        )

    if artifact_type == "slide_thumbnail":
        return (
            f"CONTEXT: We are building a thumbnail about '{topic}' for a {audience} audience.\n"
            f"TONE: {tone}\n"
            f"SCENE MODE: {scene_mode}\n"
            f"SCENE TITLE: {scene_title}\n"
            f"SCENE GOAL: {scene_goal}\n"
            f"HOOK / TAKEAWAY: {narration_focus}\n"
            f"LAYOUT TEMPLATE: {layout_template or 'hero_thumbnail'}\n"
            f"FOCAL SUBJECT: {focal_subject or topic}\n"
            f"{claim_refs_block}"
            f"{claim_text_block}"
            f"VISUAL STYLE: {style_guide}\n"
            f"VISUAL DIRECTION: {visual_prompt}\n\n"
            f"{hierarchy_block}"
            f"{crop_safe_block}"
            f"{continuity_block}"
            f"{constraints_block}"
            "ARTIFACT RULE: This output is a single slide thumbnail, not a storyboard frame and not an information poster.\n"
            "GROUNDING RULES:\n"
            "1) Use the source claims to choose a literal, domain-grounded subject or situation.\n"
            "2) Do NOT use generic symbols like compasses, chess pieces, padlocks, light bulbs, generic holograms, floating wireframes, or cosmic abstractions unless they are explicitly source-grounded.\n"
            "3) If the topic is abstract, show one concrete scenario, object, or moment that implies the claim.\n"
            "THUMBNAIL RULES:\n"
            "1) Compose one bold hero frame with one dominant subject.\n"
            "2) Create a clear text-safe zone for a future headline overlay.\n"
            "3) Make the image read instantly at small size.\n"
            "4) Favor strong silhouette, contrast, emotional clarity, and one supporting context cue.\n"
            "5) Do not spread attention across multiple equal subjects or multiple story beats.\n"
            "6) Do not create dense infographic or poster layouts.\n"
            "7) Avoid tiny details that disappear when scaled down.\n"
            "8) The image should feel click-worthy, clean, and immediate.\n\n"
            "TASK: Generate the content for THIS THUMBNAIL ONLY.\n"
            "STRICT OUTPUT RULES:\n"
            "1) Start immediately with brief support copy. NO labels, NO markdown, NO scene numbers.\n"
            f"2) The text must be {min_words}-{max_words} words.\n"
            "3) The text must explain the hook and why the visual frame is compelling.\n"
            "4) Immediately after the text, generate the corresponding high-quality inline image.\n"
            "5) The image MUST be a single composed thumbnail frame that matches the visual direction.\n"
            "6) DO NOT output any other text or conversational filler."
        )

    return (
        f"CONTEXT: We are building an explainer about '{topic}' for a {audience} audience.\n"
        f"TONE: {tone}\n"
        f"SCENE MODE: {scene_mode}\n"
        f"SCENE TITLE: {scene_title}\n"
        f"SCENE FOCUS: {narration_focus}\n"
        f"{claim_refs_block}"
        f"{claim_text_block}"
        f"{evidence_text_block}"
        f"VISUAL STYLE: {style_guide}\n"
        f"VISUAL DIRECTION: {visual_prompt}\n\n"
        f"{continuity_block}"
        f"{constraints_block}"
        "GROUNDING RULES:\n"
        "1) Use SOURCE CLAIMS and SOURCE EVIDENCE to choose concrete people, settings, objects, charts, and actions.\n"
        "2) Prefer specific nouns, measurements, environments, and interactions from the evidence over generic symbolism.\n"
        "3) Avoid generic corporate, cosmic, or metaphor-only imagery unless it is explicitly grounded in the source.\n\n"
        "CRITICAL CONTINUITY RULE: All generated images MUST share an identical, cohesive visual style. "
        "Maintain the exact same art direction as previous scenes.\n\n"
        "TASK: Generate the content for THIS SCENE ONLY.\n"
        "STRICT OUTPUT RULES:\n"
        "1) Start immediately with the spoken narration text. NO labels like 'Narration:', "
        "NO scene numbers, NO markdown titles.\n"
        f"2) The text must be {min_words}-{max_words} words.\n"
        "3) Immediately after the text, generate the corresponding high-quality inline image. "
        "The image MUST accurately depict the specific scientific or historical details mentioned in the text.\n"
        "4) Staying under the word cap is mandatory. Compress detail rather than exceeding the limit.\n"
        "5) DO NOT output any other text or conversational filler."
    )


def continuity_hints_from_scene_context(
    prior_scene_context: list[WorkflowSceneContextRequest],
) -> list[str]:
    continuity_hints: list[str] = []
    for item in prior_scene_context[-3:]:
        title = item.title.strip() or item.scene_id
        text = re.sub(r"\s+", " ", item.text or "").strip()
        if not text:
            continue
        anchor_terms = extract_anchor_terms(text, limit=4)
        if anchor_terms:
            continuity_hints.append(f"{title}: {', '.join(anchor_terms)}")
    return continuity_hints[-3:]


def workflow_scene_override_constraints(
    instruction: str,
    current_text: str,
) -> list[str]:
    normalized_instruction = re.sub(r"\s+", " ", instruction).strip()
    constraints = [
        (
            "Apply this workflow-aware director override while staying aligned with the locked "
            f"scene plan: {normalized_instruction}"
        ),
        (
            "Preserve the scene's claim coverage, evidence grounding, and artifact role unless "
            "the override explicitly asks to change emphasis."
        ),
    ]
    normalized_current_text = re.sub(r"\s+", " ", current_text).strip()
    if normalized_current_text:
        current_text_excerpt = normalized_current_text[:800]
        if len(normalized_current_text) > 800:
            current_text_excerpt = f"{current_text_excerpt.rstrip()}..."
        constraints.append(
            "Revise this current generated narration draft when helpful instead of starting from "
            f"scratch: {current_text_excerpt}"
        )
    return constraints


def build_regenerate_scene_prompt(
    *,
    scene_id: str,
    instruction: str,
    current_text: str,
    style_guide: str,
) -> str:
    return (
        f"Regenerate scene {scene_id} with this instruction: {instruction}\n\n"
        f"Original text context: {current_text}\n\n"
        "Requirements:\n"
        "1) Return updated narration text first (no labels or markdown).\n"
        "2) Then return one high-quality inline image for that scene. "
        "The image MUST accurately depict any specific scientific or historical details mentioned in the text.\n"
        f"3) Follow this visual style guide: {style_guide}"
    )
