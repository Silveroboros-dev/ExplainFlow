import json
import re
from typing import Any
from uuid import uuid4

from app.schemas.requests import (
    QuickArtifactBlockSchema,
    QuickArtifactSchema,
    QuickReelSchema,
    QuickReelSegmentSchema,
    SourceManifestSchema,
    SourceMediaRefSchema,
)
from app.services.story_agent_quick import quick_grounded_claim_cards


def quick_reel_media_key(
    media: SourceMediaRefSchema,
) -> tuple[str, int | None, int | None, int | None, tuple[float, ...]]:
    return (
        media.asset_id,
        media.start_ms,
        media.end_ms,
        media.page_index,
        tuple(float(value) for value in (media.bbox_norm or [])),
    )


def quick_reel_caption_text(text: str, *, fallback: str = "") -> str:
    cleaned = re.sub(r"\s+", " ", text).strip() or fallback.strip()
    if not cleaned:
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    if len(sentences) >= 2:
        caption = " ".join(sentences[:2])
    elif sentences:
        caption = sentences[0]
    else:
        caption = cleaned
    if len(caption) <= 220:
        return caption
    clipped = caption[:217].rsplit(" ", 1)[0].strip()
    return f"{clipped}..." if clipped else f"{caption[:217]}..."


def select_quick_reel_media_for_block(
    *,
    block: QuickArtifactBlockSchema,
    used_media_keys: set[tuple[str, int | None, int | None, int | None, tuple[float, ...]]],
) -> SourceMediaRefSchema | None:
    if not block.source_media:
        return None

    block_claim_refs = {claim_ref for claim_ref in block.claim_refs if claim_ref}
    block_evidence_refs = {evidence_ref for evidence_ref in block.evidence_refs if evidence_ref}

    def rank(media: SourceMediaRefSchema) -> tuple[int, int, int, int, int]:
        media_key = quick_reel_media_key(media)
        claim_overlap = len(block_claim_refs & {claim_ref for claim_ref in media.claim_refs if claim_ref})
        evidence_overlap = len(block_evidence_refs & {evidence_ref for evidence_ref in media.evidence_refs if evidence_ref})
        duplicate_score = 0 if media_key in used_media_keys else 1
        modality_score = {
            "video": 4,
            "audio": 3,
            "image": 2,
            "pdf_page": 1,
        }.get(media.modality, 0)
        usage_score = 1 if media.usage == "proof_clip" else 0
        return claim_overlap, evidence_overlap, duplicate_score, modality_score, usage_score

    return max(block.source_media, key=rank)


def build_quick_reel_segment(
    *,
    artifact: QuickArtifactSchema,
    block: QuickArtifactBlockSchema,
    index: int,
    used_media_keys: set[tuple[str, int | None, int | None, int | None, tuple[float, ...]]],
) -> QuickReelSegmentSchema:
    primary_media = select_quick_reel_media_for_block(
        block=block,
        used_media_keys=used_media_keys,
    )
    if primary_media is not None:
        used_media_keys.add(quick_reel_media_key(primary_media))

    fallback_image_url = (block.image_url or "").strip() or None
    if primary_media is not None and fallback_image_url:
        render_mode = "hybrid"
    elif primary_media is not None:
        render_mode = "source_clip"
    else:
        render_mode = "generated_image"

    return QuickReelSegmentSchema(
        segment_id=f"{artifact.artifact_id}-segment-{index}",
        block_id=block.block_id,
        title=block.title,
        render_mode=render_mode,
        caption_text=quick_reel_caption_text(
            block.body,
            fallback=block.title,
        ),
        claim_refs=list(block.claim_refs),
        evidence_refs=list(block.evidence_refs),
        primary_media=primary_media,
        fallback_image_url=fallback_image_url,
        start_ms=primary_media.start_ms if primary_media is not None else None,
        end_ms=primary_media.end_ms if primary_media is not None else None,
        timing_inferred=bool(primary_media.timing_inferred) if primary_media is not None else False,
    )


def build_quick_reel_from_artifact(
    *,
    artifact: QuickArtifactSchema,
    content_signal: dict[str, Any] | None,
    source_manifest: SourceManifestSchema | dict[str, Any] | None,
) -> QuickReelSchema:
    _ = source_manifest
    used_media_keys: set[tuple[str, int | None, int | None, int | None, tuple[float, ...]]] = set()
    segments = [
        build_quick_reel_segment(
            artifact=artifact,
            block=block,
            index=index,
            used_media_keys=used_media_keys,
        )
        for index, block in enumerate(artifact.blocks, start=1)
    ]
    grounded_claim_count = len(
        [
            claim
            for claim in (content_signal or {}).get("key_claims", [])
            if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
        ]
    )
    summary = (
        f"{len(segments)} ordered reel segment"
        f"{'' if len(segments) == 1 else 's'} derived from the current Quick artifact"
        + (
            f" and grounded against {grounded_claim_count} extracted claim"
            f"{'' if grounded_claim_count == 1 else 's'}."
            if grounded_claim_count
            else "."
        )
    )
    return QuickReelSchema(
        reel_id=f"{artifact.artifact_id}-reel",
        title=f"{artifact.title} proof reel",
        summary=summary,
        segments=segments,
    )


def fallback_quick_artifact(
    *,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    content_signal: dict[str, Any] | None = None,
) -> QuickArtifactSchema:
    tone_label = tone.strip() or "clear"
    claim_cards = quick_grounded_claim_cards(content_signal)
    fallback_claims = [card["claim_id"] for card in claim_cards]
    thesis = str((content_signal or {}).get("thesis", {}).get("one_liner", "")).strip()
    summary = (
        thesis
        or f"This quick artifact frames the topic for {audience} in a {tone_label} tone, using one strong hook and three supporting modules."
    )
    return QuickArtifactSchema(
        artifact_id=f"quick-{uuid4().hex[:8]}",
        title=topic.strip() or "Quick Explainer",
        subtitle=f"A fast ExplainFlow draft for {audience}.",
        summary=summary,
        visual_style=visual_mode,
        hero_direction=f"Clean {visual_mode} hero treatment that makes {topic.strip() or 'the topic'} instantly legible.",
        blocks=[
            QuickArtifactBlockSchema(
                block_id="block-1",
                label="Hook",
                title="Why this matters",
                body=(claim_cards[0]["claim_text"] if claim_cards else f"Open with the single most important shift or tension inside {topic.strip() or 'the topic'}."),
                bullets=["Name the central question.", "Establish the point of view."],
                visual_direction="Bold opener with one dominant focal cue.",
                emphasis="hook",
                claim_refs=fallback_claims[:1],
            ),
            QuickArtifactBlockSchema(
                block_id="block-2",
                label="Core Idea",
                title="What is happening",
                body=(claim_cards[1]["claim_text"] if len(claim_cards) > 1 else "Define the core mechanism or concept in plain language before adding nuance."),
                bullets=["State the mechanism clearly.", "Avoid jargon unless it earns its place."],
                visual_direction="Simple explanatory panel with one central diagram.",
                emphasis="core",
                claim_refs=fallback_claims[1:3],
            ),
            QuickArtifactBlockSchema(
                block_id="block-3",
                label="Proof",
                title="What supports it",
                body=(
                    claim_cards[2]["evidence_summary"]
                    if len(claim_cards) > 2 and claim_cards[2]["evidence_summary"]
                    else "Bring in the strongest evidence, comparison, or observed pattern that backs the claim."
                ),
                bullets=["Use one decisive support point.", "Show why the support matters."],
                visual_direction="Evidence block with one chart or comparison cue.",
                emphasis="proof",
                claim_refs=fallback_claims[2:4] or fallback_claims[:1],
            ),
            QuickArtifactBlockSchema(
                block_id="block-4",
                label="Takeaway",
                title="What to do with it",
                body=(claim_cards[3]["claim_text"] if len(claim_cards) > 3 else "End on the practical implication, takeaway, or decision the audience should leave with."),
                bullets=["Translate insight into action.", "Keep the close memorable."],
                visual_direction="Closing module with synthesis and one action cue.",
                emphasis="action",
                claim_refs=fallback_claims[3:5] or fallback_claims[:1],
            ),
        ],
    )


def normalize_quick_artifact(
    artifact: QuickArtifactSchema,
    *,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    content_signal: dict[str, Any] | None = None,
) -> QuickArtifactSchema:
    blocks = artifact.blocks[:4]
    fallback = fallback_quick_artifact(
        topic=topic,
        audience=audience,
        tone=tone,
        visual_mode=visual_mode,
        content_signal=content_signal,
    )
    valid_claim_ids = {
        str(claim.get("claim_id", "")).strip()
        for claim in (content_signal or {}).get("key_claims", [])
        if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
    }
    used_ids: set[str] = set()
    normalized_blocks: list[QuickArtifactBlockSchema] = []
    for idx, block in enumerate(blocks, start=1):
        block_id = (block.block_id or "").strip() or f"block-{idx}"
        if block_id in used_ids:
            block_id = f"block-{idx}"
        used_ids.add(block_id)
        normalized_blocks.append(
            QuickArtifactBlockSchema(
                block_id=block_id,
                label=(block.label or "").strip() or fallback.blocks[idx - 1].label,
                title=(block.title or "").strip() or fallback.blocks[idx - 1].title,
                body=(block.body or "").strip() or fallback.blocks[idx - 1].body,
                bullets=[bullet.strip() for bullet in block.bullets[:3] if isinstance(bullet, str) and bullet.strip()] or fallback.blocks[idx - 1].bullets,
                visual_direction=(block.visual_direction or "").strip() or fallback.blocks[idx - 1].visual_direction,
                image_url=(block.image_url or "").strip() or None,
                emphasis=block.emphasis,
                claim_refs=[
                    ref for ref in block.claim_refs
                    if isinstance(ref, str) and ref.strip() and (not valid_claim_ids or ref.strip() in valid_claim_ids)
                ] or fallback.blocks[idx - 1].claim_refs,
                evidence_refs=[],
                source_media=[],
            )
        )
    while len(normalized_blocks) < 4:
        normalized_blocks.append(fallback.blocks[len(normalized_blocks)])
    return QuickArtifactSchema(
        artifact_id=(artifact.artifact_id or "").strip() or fallback.artifact_id,
        title=(artifact.title or "").strip() or fallback.title,
        subtitle=(artifact.subtitle or "").strip() or fallback.subtitle,
        summary=(artifact.summary or "").strip() or fallback.summary,
        visual_style=(artifact.visual_style or "").strip() or visual_mode,
        hero_direction=(artifact.hero_direction or "").strip() or fallback.hero_direction,
        hero_image_url=artifact.hero_image_url,
        blocks=normalized_blocks,
    )


def build_quick_artifact_prompt(
    *,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    style_guide: str,
    content_signal: dict[str, Any] | None,
    source_excerpt: str,
) -> str:
    claim_cards = quick_grounded_claim_cards(content_signal)
    claim_block = ""
    if claim_cards:
        claim_block = "GROUNDED CLAIMS:\n" + "\n".join(
            f"- {card['claim_id']}: {card['claim_text']}" + (f" | evidence: {card['evidence_summary']}" if card["evidence_summary"] else "")
            for card in claim_cards[:6]
        ) + "\n\n"
    source_excerpt_block = (
        "SOURCE EXCERPT:\n"
        f"{source_excerpt}\n\n"
        if source_excerpt
        else ""
    )
    return (
        "You are creating a fast ExplainFlow quick artifact.\n"
        "Return only valid JSON matching the schema.\n"
        "This is the lightweight Quick mode, so optimize for immediacy, clarity, and HTML-first rendering rather than scene-by-scene production.\n\n"
        f"TOPIC: {topic}\n"
        f"AUDIENCE: {audience}\n"
        f"TONE: {tone or 'clear and practical'}\n"
        f"VISUAL MODE: {visual_mode}\n"
        f"STYLE GUIDE: {style_guide}\n\n"
        f"{claim_block}"
        f"{source_excerpt_block}"
        "Requirements:\n"
        "- Create exactly 4 blocks.\n"
        "- Make the artifact publishable as a compact structured explainer.\n"
        "- Use one strong hook, two support blocks, and one takeaway block.\n"
        "- Each block must be short, high-signal, and distinct.\n"
        "- `body` should be prose, not bullets.\n"
        "- `bullets` should contain 0 to 3 short supporting lines.\n"
        "- `visual_direction` should describe what a later visual treatment should emphasize.\n"
        "- If GROUNDED CLAIMS are provided, each block must use 1 to 3 valid `claim_refs` drawn only from those claim IDs.\n"
        "- Favor claim groupings that can later attach proof clips or source-backed proof media.\n"
        "- Do not mention JSON, scenes, or script packs in the copy.\n"
        "- Keep the artifact compact enough to feel immediate in a demo.\n"
    )


def build_quick_block_image_prompt(
    *,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    style_guide: str,
    artifact: QuickArtifactSchema,
    block: QuickArtifactBlockSchema,
    content_signal: dict[str, Any] | None,
) -> str:
    claim_lookup = {
        card["claim_id"]: card
        for card in quick_grounded_claim_cards(content_signal)
    }
    claim_lines = [
        f"- {claim_lookup[claim_ref]['claim_text']}"
        + (
            f" | evidence: {claim_lookup[claim_ref]['evidence_summary']}"
            if claim_lookup[claim_ref]["evidence_summary"]
            else ""
        )
        for claim_ref in block.claim_refs
        if claim_ref in claim_lookup
    ][:3]
    if not claim_lines and claim_lookup:
        claim_lines = [
            f"- {card['claim_text']}" + (f" | evidence: {card['evidence_summary']}" if card["evidence_summary"] else "")
            for card in list(claim_lookup.values())[:2]
        ]

    bullet_lines = [f"- {bullet}" for bullet in block.bullets[:3] if bullet.strip()]
    source_media_hints = [
        hint.strip()
        for hint in [
            *(media.label or "" for media in block.source_media[:1]),
            *(media.visual_context or "" for media in block.source_media[:1]),
            *(media.quote_text or "" for media in block.source_media[:1]),
        ]
        if hint and hint.strip()
    ]

    prompt = (
        f"CONTEXT: Create one visual module for a Quick ExplainFlow artifact about '{topic}'.\n"
        f"AUDIENCE: {audience}\n"
        f"TONE: {tone or 'clear and practical'}\n"
        f"VISUAL MODE: {visual_mode}\n"
        f"STYLE GUIDE: {style_guide}\n"
        f"ARTIFACT TITLE: {artifact.title}\n"
        f"BLOCK LABEL: {block.label}\n"
        f"BLOCK TITLE: {block.title}\n"
        f"BLOCK BODY: {block.body}\n"
        f"BLOCK EMPHASIS: {block.emphasis}\n"
        f"VISUAL DIRECTION: {block.visual_direction}\n"
    )
    if bullet_lines:
        prompt += "SUPPORTING BULLETS:\n" + "\n".join(bullet_lines) + "\n"
    if claim_lines:
        prompt += "SOURCE CLAIMS:\n" + "\n".join(claim_lines) + "\n"
    if source_media_hints:
        prompt += "SOURCE MEDIA HINTS:\n" + "\n".join(f"- {hint}" for hint in source_media_hints[:2]) + "\n"
    prompt += (
        "\nTASK:\n"
        "Generate one polished supporting visual for this single artifact block.\n"
        "The image should feel editorial, legible, and specific to the block rather than a generic stock metaphor.\n"
        "Ground the image in the source claims and media hints when available.\n"
        "Avoid tiny text, UI chrome, or multiple unrelated subjects.\n"
        "Return the image only.\n"
    )
    return prompt


def quick_override_requests_visual_refresh(
    *,
    instruction: str,
    original_block: QuickArtifactBlockSchema,
    updated_block: QuickArtifactBlockSchema,
) -> bool:
    normalized_instruction = instruction.lower()
    visual_keywords = (
        "diagram",
        "chart",
        "graphic",
        "image",
        "visual",
        "illustration",
        "frame",
        "render",
        "redraw",
        "flowchart",
        "schematic",
        "timeline",
        "map",
    )
    if any(keyword in normalized_instruction for keyword in visual_keywords):
        return True
    return updated_block.visual_direction.strip() != original_block.visual_direction.strip()


def build_quick_hero_image_prompt(
    *,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    style_guide: str,
    artifact: QuickArtifactSchema,
    content_signal: dict[str, Any] | None,
) -> str:
    claim_cards = quick_grounded_claim_cards(content_signal)
    claim_block = ""
    if claim_cards:
        claim_block = "SOURCE CLAIMS:\n" + "\n".join(
            f"- {card['claim_text']}" for card in claim_cards[:4]
        ) + "\n\n"

    return (
        f"CONTEXT: Create one hero visual for a Quick ExplainFlow artifact about '{topic}'.\n"
        f"AUDIENCE: {audience}\n"
        f"TONE: {tone or 'clear and practical'}\n"
        f"VISUAL MODE: {visual_mode}\n"
        f"STYLE GUIDE: {style_guide}\n"
        f"ARTIFACT TITLE: {artifact.title}\n"
        f"ARTIFACT SUMMARY: {artifact.summary}\n"
        f"HERO DIRECTION: {artifact.hero_direction}\n\n"
        f"{claim_block}"
        "TASK:\n"
        "Generate a single polished hero image for the artifact.\n"
        "The image should feel immediate, legible, and presentation-ready.\n"
        "Ground the subject in the source claims when they are available.\n"
        "Avoid generic cosmic/corporate symbolism unless explicitly grounded.\n"
        "Return the image only.\n"
    )


def build_quick_block_override_prompt(
    *,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    artifact: QuickArtifactSchema,
    target_block: QuickArtifactBlockSchema,
    instruction: str,
    content_signal: dict[str, Any] | None,
) -> str:
    claim_cards = quick_grounded_claim_cards(content_signal)
    companion_blocks = [
        {
            "block_id": block.block_id,
            "label": block.label,
            "title": block.title,
            "emphasis": block.emphasis,
        }
        for block in artifact.blocks
        if block.block_id != target_block.block_id
    ]
    return (
        "You are applying a director override to one block inside an ExplainFlow quick artifact.\n"
        "Return only valid JSON for the updated block.\n"
        "Rewrite only the target block. Do not rewrite the rest of the artifact.\n"
        "Preserve the same block_id.\n"
        "Keep the block aligned with the artifact tone, audience, and visual mode.\n"
        "Do not invent unrelated claims or drift away from the topic.\n\n"
        f"TOPIC: {topic}\n"
        f"AUDIENCE: {audience}\n"
        f"TONE: {tone or 'clear and practical'}\n"
        f"VISUAL MODE: {visual_mode}\n"
        f"GROUNDED CLAIMS: {json.dumps(claim_cards[:6])}\n"
        f"ARTIFACT TITLE: {artifact.title}\n"
        f"ARTIFACT SUMMARY: {artifact.summary}\n"
        f"OTHER BLOCKS: {json.dumps(companion_blocks)}\n"
        f"TARGET BLOCK: {target_block.model_dump_json()}\n"
        f"DIRECTOR NOTE: {instruction}\n"
    )


def normalize_quick_override_block(
    *,
    target_block: QuickArtifactBlockSchema,
    updated_block: QuickArtifactBlockSchema,
) -> QuickArtifactBlockSchema:
    return QuickArtifactBlockSchema(
        block_id=target_block.block_id,
        label=(updated_block.label or "").strip() or target_block.label,
        title=(updated_block.title or "").strip() or target_block.title,
        body=(updated_block.body or "").strip() or target_block.body,
        bullets=[bullet.strip() for bullet in updated_block.bullets[:3] if isinstance(bullet, str) and bullet.strip()] or target_block.bullets,
        visual_direction=(updated_block.visual_direction or "").strip() or target_block.visual_direction,
        image_url=target_block.image_url,
        emphasis=updated_block.emphasis,
        claim_refs=[ref for ref in updated_block.claim_refs if isinstance(ref, str) and ref.strip()] or target_block.claim_refs,
        evidence_refs=list(target_block.evidence_refs),
        source_media=list(target_block.source_media),
    )


def build_quick_artifact_override_prompt(
    *,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    artifact: QuickArtifactSchema,
    instruction: str,
    content_signal: dict[str, Any] | None,
    anchor_block_id: str | None,
    anchor_index: int,
) -> str:
    claim_cards = quick_grounded_claim_cards(content_signal)
    preserved_blocks = [block.model_dump() for block in artifact.blocks[:anchor_index]]
    editable_blocks = [block.model_dump() for block in artifact.blocks[anchor_index:]]
    return (
        "You are applying a global director override to an ExplainFlow quick artifact.\n"
        "Return only valid JSON matching the artifact schema.\n"
        "Keep the artifact compact, high-signal, and HTML-first.\n"
        "Preserve the same number of blocks and preserve all existing block_ids.\n"
        "If preserved blocks are provided, leave them unchanged and only rewrite the editable blocks.\n"
        "Do not invent unrelated claims or drift away from the topic.\n\n"
        f"TOPIC: {topic}\n"
        f"AUDIENCE: {audience}\n"
        f"TONE: {tone or 'clear and practical'}\n"
        f"VISUAL MODE: {visual_mode}\n"
        f"GROUNDED CLAIMS: {json.dumps(claim_cards[:6])}\n"
        f"CURRENT ARTIFACT: {artifact.model_dump_json()}\n"
        f"PRESERVED BLOCKS: {json.dumps(preserved_blocks)}\n"
        f"EDITABLE BLOCKS: {json.dumps(editable_blocks)}\n"
        f"ANCHOR BLOCK ID: {anchor_block_id or 'rewrite_entire_artifact'}\n"
        f"DIRECTOR NOTE: {instruction}\n"
    )


def merge_regenerated_quick_artifact(
    *,
    original_artifact: QuickArtifactSchema,
    normalized_artifact: QuickArtifactSchema,
    anchor_index: int,
) -> QuickArtifactSchema:
    if anchor_index > 0:
        preserved = original_artifact.blocks[:anchor_index]
        regenerated = normalized_artifact.blocks[anchor_index:]
        return QuickArtifactSchema(
            artifact_id=original_artifact.artifact_id,
            title=original_artifact.title,
            subtitle=original_artifact.subtitle,
            summary=original_artifact.summary,
            visual_style=normalized_artifact.visual_style,
            hero_direction=original_artifact.hero_direction,
            blocks=[*preserved, *regenerated],
        )

    return QuickArtifactSchema(
        artifact_id=original_artifact.artifact_id,
        title=normalized_artifact.title,
        subtitle=normalized_artifact.subtitle,
        summary=normalized_artifact.summary,
        visual_style=normalized_artifact.visual_style,
        hero_direction=normalized_artifact.hero_direction,
        blocks=normalized_artifact.blocks,
    )
