from copy import deepcopy
import json
from typing import Any


def build_signal_extraction_prompt(
    *,
    document_text: str,
    schema_text: str,
    version: str,
    source_inventory_text: str = "",
    transcript_only_video: bool = False,
) -> str:
    source_body = document_text.strip() or "Use the uploaded source media as the primary source of truth."
    source_inventory_block = (
        f"\n\nSOURCE ASSET INVENTORY:\n{source_inventory_text.strip()}"
        if source_inventory_text.strip()
        else ""
    )
    multimodal_rules = (
        "5) If evidence comes from uploaded media, prefer structured evidence_snippets with type, asset_id, "
        "and start_ms/end_ms or page_index when available.\n"
        "6) For image or document evidence, use visual_context and page_index instead of inventing exact crops.\n"
        "7) For audio or video, use transcript/captions as the primary truth layer for claims.\n"
        "8) If a speaker refers deictically to the screen (for example 'this chart' or 'as you can see'), "
        "resolve that reference into explicit visual_context at the same timestamp.\n"
        "9) When speaker identity is knowable from the media, populate speaker for the evidence snippet.\n"
        "10) For video, only use frames to resolve on-screen references, clip-worthy moments, and proof playback. "
        "Do not replace transcript-grounded claims with vague visual summaries.\n"
        "11) For PDFs or document uploads, do not anchor most claims to the abstract, executive summary, or page 1 "
        "if later body pages provide stronger support.\n"
        "12) Prefer diverse body-page evidence across distinct claims. Use frontmatter evidence mainly for opener "
        "context, unless the source is genuinely one-page or only frontmatter contains the claim.\n"
        "13) EVIDENCE SELECTION RULE: If a claim appears on page 1 and is later proven, detailed, or debated on a "
        "body page, you MUST cite the body-page evidence snippet instead of the summary mention.\n"
        if source_inventory_text.strip()
        else ""
    )
    transcript_only_guardrail = (
        "14) This source path is transcript-backed video without direct frame access.\n"
        "15) If the transcript says 'this chart', 'as you can see', or similar, do not invent exact on-screen visuals. "
        "Infer only what surrounding text supports, or keep visual_context generic.\n"
        if transcript_only_video
        else ""
    )
    if version == "v1":
        return (
            "Analyze the following document and extract the core signal into a highly structured JSON format.\n"
            "You MUST strictly adhere to the provided JSON Schema.\n\n"
            f"DOCUMENT:\n{source_body}\n"
            f"{source_inventory_block}\n\n"
            f"JSON SCHEMA:\n{schema_text}\n\n"
            "Return ONLY valid JSON matching this schema, without any markdown formatting like ```json."
        )

    return (
        "SYSTEM:\n"
        "You are a narrative signal extractor for ExplainFlow.\n"
        "Do NOT write a story. Do NOT add facts not present in the source.\n\n"
        "TASK:\n"
        "Extract a style-agnostic Narrative Signal Inventory from SOURCE in ONE RUN.\n"
        "Do all reasoning internally, then output only final JSON that matches the schema.\n\n"
        "GROUNDING RULES:\n"
        "1) Every key claim must be source-grounded.\n"
        "2) Include short evidence quotes for claims (<=12 words each).\n"
        "3) If support is weak or missing, lower confidence and mark uncertainty in supporting_points.\n"
        "4) If unresolved ambiguity remains, add an item to open_questions.\n\n"
        f"{multimodal_rules}"
        f"{transcript_only_guardrail}"
        "INTERNAL PROCEDURE (do internally, no extra output fields):\n"
        "1) Segment source into event units.\n"
        "2) Build canonical entity/concept ledger with aliases merged.\n"
        "3) Build event frames (actors, goals, outcomes, state changes).\n"
        "4) Identify discourse links (cause, contrast, concession, escalation).\n"
        "5) Score salience with centrality, stakes, surprise, causal leverage, transformation.\n"
        "6) Select non-redundant top signals with coverage across major plotlines/entities.\n\n"
        "MAPPING TO SCHEMA (critical):\n"
        "- key_claims: concise, non-duplicate claims with evidence_snippets and calibrated confidence (0..1).\n"
        "- concepts: canonical concepts only (merge synonyms/aliases).\n"
        "- narrative_beats: coherent progression (3..8 beats) with valid claim_refs.\n"
        "- visual_candidates: practical structures tied to claim_refs.\n"
        "- signal_quality: coverage_score, ambiguity_score, hallucination_risk consistent with extraction quality.\n"
        "- ID integrity: claim_id c1.., concept_id k1.., candidate_id v1.., beat_id b1.., and all refs valid.\n\n"
        "STRICT OUTPUT:\n"
        "Return ONLY valid JSON matching the schema exactly.\n"
        "No markdown, no prose, no additional keys.\n\n"
        f"SOURCE:\n{source_body}"
        f"{source_inventory_block}\n\n"
        f"JSON SCHEMA:\n{schema_text}"
    )


def transcript_needs_normalization(text: str) -> bool:
    sample = str(text or "").strip()
    if len(sample) < 120:
        return False
    punctuation_count = sum(sample.count(mark) for mark in ".?!")
    line_break_count = sample.count("\n")
    long_run = len(max(sample.splitlines() or [sample], key=len, default=""))
    return punctuation_count <= max(1, len(sample) // 500) or (line_break_count <= 1 and long_run > 220)


def build_transcript_normalization_prompt(
    *,
    transcript_text: str,
    source_inventory_text: str = "",
) -> str:
    inventory_block = (
        f"\n\nSOURCE ASSET INVENTORY:\n{source_inventory_text.strip()}"
        if source_inventory_text.strip()
        else ""
    )
    return (
        "SYSTEM:\n"
        "You normalize rough transcript or caption text for ExplainFlow.\n"
        "Return JSON only.\n\n"
        "TASK:\n"
        "Rewrite the transcript into clean reading-order text with punctuation, paragraph breaks, and light speaker segmentation when obviously inferable.\n\n"
        "RULES:\n"
        "1) Do not summarize.\n"
        "2) Do not drop specific nouns, figures, measurements, or technical terms.\n"
        "3) Preserve timestamps only if they are already embedded inline; otherwise omit them.\n"
        "4) If the transcript references unseen visuals like 'this chart' or 'as you can see', keep the language but do not invent what is on screen.\n"
        "5) Output readable prose that remains faithful to the source transcript.\n\n"
        "OUTPUT JSON:\n"
        "{\n"
        '  "normalized_source_text": "string",\n'
        '  "source_text_origin": "youtube_transcript_normalized|video_transcript_normalized"\n'
        "}\n\n"
        f"TRANSCRIPT:\n{transcript_text.strip()}{inventory_block}"
    )


def should_use_text_backed_fast_extraction(
    *,
    normalized_source_text: str,
    uploaded_asset_count: int,
) -> bool:
    return bool(str(normalized_source_text or "").strip()) and uploaded_asset_count == 0


def build_source_text_recovery_prompt(
    *,
    source_inventory_text: str = "",
) -> str:
    inventory_block = (
        f"\n\nSOURCE ASSET INVENTORY:\n{source_inventory_text.strip()}"
        if source_inventory_text.strip()
        else ""
    )
    return (
        "SYSTEM:\n"
        "You recover clean reading-order source text for ExplainFlow.\n"
        "Return JSON only.\n\n"
        "TASK:\n"
        "Read the uploaded source assets and recover normalized source text that preserves the author's wording, "
        "specific nouns, concrete settings, and key factual phrases in clean reading order.\n\n"
        "RULES:\n"
        "1) Do not summarize.\n"
        "2) Do not paraphrase unless the original is unreadable.\n"
        "3) Keep section headings when helpful.\n"
        "4) Omit repeated page furniture, page numbers, and boilerplate navigation text.\n"
        "5) If the source is audio, transcribe the spoken content in readable order.\n"
        "6) If the source is a PDF or image, prefer exact readable text over guesses.\n\n"
        "OUTPUT JSON:\n"
        "{\n"
        '  "normalized_source_text": "string",\n'
        '  "source_text_origin": "pdf_text|ocr|audio_transcript|gemini_asset_text"\n'
        "}\n\n"
        f"SOURCE MEDIA:{inventory_block}"
    )


def build_structural_signal_prompt(
    *,
    document_text: str,
    source_inventory_text: str = "",
    transcript_only_video: bool = False,
) -> str:
    inventory_block = (
        f"\n\nSOURCE ASSET INVENTORY:\n{source_inventory_text.strip()}"
        if source_inventory_text.strip()
        else ""
    )
    source_body = document_text.strip() or "Use the uploaded source media as the source of truth."
    transcript_guardrail = (
        "7) This source path is transcript-backed video without direct frame access. "
        "If the transcript references on-screen visuals ('this chart', 'here on the screen'), do not invent exact visual details. "
        "Infer only what surrounding transcript language supports.\n\n"
        if transcript_only_video
        else ""
    )
    return (
        "SYSTEM:\n"
        "You extract the structural truth layer for ExplainFlow.\n"
        "Return JSON only.\n\n"
        "TASK:\n"
        "Using SOURCE TEXT as the primary reading-order reference, extract only the grounded structural layer.\n\n"
        "OUTPUT KEYS:\n"
        "- version\n"
        "- source\n"
        "- thesis\n"
        "- key_claims\n"
        "- concepts\n"
        "- open_questions\n"
        "- signal_quality\n\n"
        "DO NOT OUTPUT:\n"
        "- narrative_beats\n"
        "- visual_candidates\n\n"
        "GROUNDING RULES:\n"
        "1) Every key claim must be source-grounded.\n"
        "2) Keep specific nouns, actors, settings, and measurements from the source.\n"
        "3) Include evidence_snippets for claims.\n"
        "4) If uploaded media is available, use structured evidence_snippets with type, asset_id, and page_index/start_ms/end_ms when supported.\n"
        "5) Lower confidence when support is weak.\n"
        "6) Do not invent facts, beats, or visuals.\n"
        "7) For PDFs or documents, prefer later body-page evidence when it supports the claim more directly than the abstract or page 1.\n"
        "8) Avoid anchoring most claims to abstract/frontmatter evidence unless the claim genuinely appears only there.\n"
        "9) If a claim is summarized on page 1 but substantiated later, cite the later body page in evidence_snippets.\n"
        f"{transcript_guardrail}"
        "SOURCE:\n"
        f"{source_body}"
        f"{inventory_block}\n"
    )


def build_creative_signal_prompt(
    *,
    document_text: str,
    structural_signal: dict[str, Any],
    transcript_only_video: bool = False,
) -> str:
    claim_ids = [
        str(claim.get("claim_id", "")).strip()
        for claim in structural_signal.get("key_claims", [])
        if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
    ]
    transcript_guardrail = (
        "7) This source path is transcript-backed video without direct frame access. "
        "Do not claim you saw the screen. If transcript references on-screen visuals, keep the candidate conceptual or transcript-grounded rather than visually specific.\n\n"
        if transcript_only_video
        else ""
    )
    return (
        "SYSTEM:\n"
        "You create the creative structuring layer for ExplainFlow.\n"
        "Return JSON only.\n\n"
        "TASK:\n"
        "Using the grounded structural signal and SOURCE TEXT, produce only narrative_beats and visual_candidates.\n\n"
        "OUTPUT JSON:\n"
        "{\n"
        '  "narrative_beats": [...],\n'
        '  "visual_candidates": [...]\n'
        "}\n\n"
        "RULES:\n"
        f"1) You may reference only these claim IDs: {', '.join(claim_ids) if claim_ids else 'none'}.\n"
        "2) Do not invent new claims.\n"
        "3) Beats must be concrete, source-grounded, and useful for sequencing scenes.\n"
        "4) Visual candidates must be practical structures tied to claim_refs.\n"
        "5) Preserve vivid, concrete source language when it helps visual specificity.\n"
        "6) Avoid generic corporate or symbolic visuals unless the source explicitly suggests them.\n"
        f"{transcript_guardrail}"
        "SOURCE TEXT:\n"
        f"{document_text.strip()}\n\n"
        "STRUCTURAL SIGNAL:\n"
        f"{json.dumps(structural_signal, ensure_ascii=True)}"
    )


def build_fallback_narrative_beats(
    *,
    structural_signal: dict[str, Any],
) -> list[dict[str, Any]]:
    claims = [
        claim
        for claim in structural_signal.get("key_claims", [])
        if isinstance(claim, dict) and str(claim.get("claim_text", "")).strip()
    ]
    thesis = str(structural_signal.get("thesis", {}).get("one_liner", "")).strip()
    beat_specs: list[tuple[str, str, list[str]]] = []
    if thesis:
        first_claim_id = str(claims[0].get("claim_id", "")).strip() if claims else ""
        beat_specs.append(("hook", thesis, [first_claim_id] if first_claim_id else []))
    if claims:
        middle_claim = claims[min(1, len(claims) - 1)]
        beat_specs.append(
            (
                "mechanism",
                str(middle_claim.get("claim_text", "")).strip(),
                [str(middle_claim.get("claim_id", "")).strip()],
            )
        )
        last_claim = claims[-1]
        beat_specs.append(
            (
                "takeaway",
                str(last_claim.get("claim_text", "")).strip(),
                [str(last_claim.get("claim_id", "")).strip()],
            )
        )
    cleaned_specs = [
        (role, message, [claim_ref for claim_ref in claim_refs if claim_ref])
        for role, message, claim_refs in beat_specs
        if message
    ]
    if len(cleaned_specs) < 3 and claims:
        fallback_claim = claims[0]
        fallback_claim_id = str(fallback_claim.get("claim_id", "")).strip()
        fallback_message = str(fallback_claim.get("claim_text", "")).strip()
        while len(cleaned_specs) < 3 and fallback_message:
            cleaned_specs.append(("context", fallback_message, [fallback_claim_id] if fallback_claim_id else []))
    beats: list[dict[str, Any]] = []
    for index, (role, message, claim_refs) in enumerate(cleaned_specs[:8], start=1):
        beats.append(
            {
                "beat_id": f"b{index}",
                "role": role,
                "message": message,
                "claim_refs": claim_refs,
            }
        )
    return beats


def build_fallback_visual_candidates(
    *,
    structural_signal: dict[str, Any],
) -> list[dict[str, Any]]:
    claims = [
        claim
        for claim in structural_signal.get("key_claims", [])
        if isinstance(claim, dict) and str(claim.get("claim_text", "")).strip()
    ]
    candidates: list[dict[str, Any]] = []
    if len(claims) >= 2:
        candidates.append(
            {
                "candidate_id": "v1",
                "purpose": "Compare the most important grounded claims.",
                "recommended_structure": "comparison",
                "data_points": [
                    str(claims[0].get("claim_text", "")).strip()[:100],
                    str(claims[1].get("claim_text", "")).strip()[:100],
                ],
                "claim_refs": [
                    str(claims[0].get("claim_id", "")).strip(),
                    str(claims[1].get("claim_id", "")).strip(),
                ],
            }
        )
    elif claims:
        candidates.append(
            {
                "candidate_id": "v1",
                "purpose": "Show the core grounded mechanism or concept.",
                "recommended_structure": "concept_map",
                "data_points": [str(claims[0].get("claim_text", "")).strip()[:100]],
                "claim_refs": [str(claims[0].get("claim_id", "")).strip()],
            }
        )
    return candidates


def merge_signal_extraction_passes(
    *,
    structural_signal: dict[str, Any],
    creative_signal: dict[str, Any],
) -> dict[str, Any]:
    merged = deepcopy(structural_signal)
    valid_claim_ids = {
        str(claim.get("claim_id", "")).strip()
        for claim in structural_signal.get("key_claims", [])
        if isinstance(claim, dict)
    }

    beats: list[dict[str, Any]] = []
    for index, beat in enumerate(creative_signal.get("narrative_beats", []), start=1):
        if not isinstance(beat, dict):
            continue
        message = str(beat.get("message", "")).strip()
        if not message:
            continue
        claim_refs = [
            str(claim_ref).strip()
            for claim_ref in beat.get("claim_refs", [])
            if str(claim_ref).strip() in valid_claim_ids
        ]
        if not claim_refs:
            continue
        beats.append(
            {
                "beat_id": str(beat.get("beat_id", "")).strip() or f"b{index}",
                "role": str(beat.get("role", "")).strip() or ("hook" if index == 1 else "takeaway"),
                "message": message,
                "claim_refs": claim_refs,
            }
        )
    if len(beats) < 3:
        beats = build_fallback_narrative_beats(structural_signal=structural_signal)

    visual_candidates: list[dict[str, Any]] = []
    valid_structures = {
        "flowchart",
        "timeline",
        "comparison",
        "matrix",
        "process",
        "architecture",
        "concept_map",
        "table",
    }
    for index, candidate in enumerate(creative_signal.get("visual_candidates", []), start=1):
        if not isinstance(candidate, dict):
            continue
        purpose = str(candidate.get("purpose", "")).strip()
        structure = str(candidate.get("recommended_structure", "")).strip()
        claim_refs = [
            str(claim_ref).strip()
            for claim_ref in candidate.get("claim_refs", [])
            if str(claim_ref).strip() in valid_claim_ids
        ]
        if not purpose or structure not in valid_structures or not claim_refs:
            continue
        visual_candidates.append(
            {
                "candidate_id": str(candidate.get("candidate_id", "")).strip() or f"v{index}",
                "purpose": purpose,
                "recommended_structure": structure,
                "data_points": [
                    str(item).strip()
                    for item in candidate.get("data_points", [])
                    if str(item).strip()
                ][:6],
                "claim_refs": claim_refs,
            }
        )
    if not visual_candidates:
        visual_candidates = build_fallback_visual_candidates(structural_signal=structural_signal)

    merged["narrative_beats"] = beats[:8]
    merged["visual_candidates"] = visual_candidates[:8]
    merged["open_questions"] = [
        str(item).strip()
        for item in (
            list(structural_signal.get("open_questions", []))
            + list(creative_signal.get("open_questions", []))
        )
        if str(item).strip()
    ][:8]
    return merged
