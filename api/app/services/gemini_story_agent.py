import asyncio
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import os
import re
import time
from typing import Any, AsyncIterator, Literal
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Request
from google.genai import types
from pydantic import BaseModel, Field

from app.config import SCHEMAS_DIR, get_gemini_client
from app.schemas.events import (
    add_checkpoint,
    add_or_update_scene_trace,
    build_checkpoint_event,
    build_sse_event,
    init_trace_envelope,
    trace_meta,
)
from app.schemas.requests import (
    AdvancedStreamRequest,
    ArtifactName,
    EvidenceRefSchema,
    OutlineSchema,
    PlannerQaSummary,
    QuickArtifactBlockSchema,
    QuickArtifactOverrideRequest,
    QuickArtifactRequest,
    QuickArtifactSchema,
    QuickBlockOverrideRequest,
    QuickReelRequest,
    QuickReelSchema,
    QuickReelSegmentSchema,
    RegenerateSceneRequest,
    SourceAssetSchema,
    SourceManifestSchema,
    SourceMediaRefSchema,
    SceneModuleSchema,
    ScenePlanSchema,
    ScriptPack,
    ScriptPackRequest,
    ScriptPackScene,
    SignalExtractionRequest,
)
from app.services.audio_pipeline import generate_audio_and_get_url
from app.services.image_pipeline import (
    asset_path_from_reference,
    crop_source_region_and_get_url,
    build_thumbnail_cover_cues,
    compose_thumbnail_cover_and_get_url,
    public_asset_url,
    save_image_and_get_url,
)
from app.services.interleaved_parser import (
    append_text_part,
    evaluate_scene_quality,
    extract_anchor_terms,
    extract_parts_from_chunk,
    extract_parts_from_response,
    normalized_scene_id,
)
from app.services.source_ingest import (
    best_effort_manifest_text,
    resolve_pdf_proof_locator,
    validate_video_manifest_constraints,
)

SIGNAL_EXTRACTION_PROMPT_VERSION_DEFAULT = "v2"
SIGNAL_STRUCTURAL_MODEL_DEFAULT = "gemini-3.1-pro-preview"
SIGNAL_CREATIVE_MODEL_DEFAULT = "gemini-3.1-pro-preview"
SIGNAL_SOURCE_TEXT_MODEL_DEFAULT = "gemini-3.1-flash-image-preview"
PLANNER_PRECOMPUTE_MODEL_DEFAULT = "gemini-3.1-flash-image-preview"
ADVANCED_SCENE_CONCURRENCY_DEFAULT = 2
QUICK_ARTIFACT_MODEL_DEFAULT = "gemini-3.1-flash-image-preview"


DEFAULT_PLANNER_ARTIFACT_TYPE = "storyboard_grid"


@dataclass(frozen=True)
class SceneBudgetPolicy:
    default: int
    minimum: int
    maximum: int
    derive_from_duration: bool
    expansion_rule: str


@dataclass(frozen=True)
class ArtifactPlanningPolicy:
    artifact_type: str
    planning_mode: str
    script_shape: str
    scene_budget: SceneBudgetPolicy
    salience_pass: str
    forward_pull_pass: str
    planner_focus: tuple[str, ...]
    generator_notes: tuple[str, ...]


class SalienceAssessmentItem(BaseModel):
    candidate_id: str
    candidate_type: str
    content: str
    rating: Literal["CRITICAL", "IMPORTANT", "FLAVOUR"]
    downstream_impact: str
    evidence_quote: str = ""
    overlap_with: list[str] = Field(default_factory=list)


class SalienceAssessmentSchema(BaseModel):
    items: list[SalienceAssessmentItem] = Field(default_factory=list)


class ForwardPullBait(BaseModel):
    content: str = ""
    evidence_quote: str = ""


class ForwardPullHook(BaseModel):
    question: str = ""
    evidence_quote: str = ""


class ForwardPullThreat(BaseModel):
    stake: str
    who_is_at_risk: str = ""
    evidence_quote: str = ""


class ForwardPullReward(BaseModel):
    payoff_signal: str
    likely_location: str = ""
    evidence_quote: str = ""


class ForwardPullPayload(BaseModel):
    theme_or_engine: str
    supporting_instances: list[str] = Field(default_factory=list)


class ForwardPullSchema(BaseModel):
    bait: ForwardPullBait | None = None
    hook: ForwardPullHook | None = None
    threats: list[ForwardPullThreat] = Field(default_factory=list)
    rewards: list[ForwardPullReward] = Field(default_factory=list)
    payloads: list[ForwardPullPayload] = Field(default_factory=list)


@dataclass(frozen=True)
class UploadedSourceAssets:
    parts: tuple[Any, ...]
    file_names: tuple[str, ...]
    count: int


@dataclass(frozen=True)
class PlannerEnrichmentContext:
    artifact_policy: ArtifactPlanningPolicy
    thesis: str
    audience_descriptor: str
    claim_ids: tuple[str, ...]
    scene_count: int
    salience_assessment: SalienceAssessmentSchema | None
    forward_pull: ForwardPullSchema | None


@dataclass(frozen=True)
class PlannerIssue:
    severity: str
    code: str
    message: str
    scene_id: str | None = None
    target: str | None = None


@dataclass(frozen=True)
class PlannerValidationReport:
    hard_issues: tuple[PlannerIssue, ...]
    warnings: tuple[PlannerIssue, ...]

    @property
    def has_hard_issues(self) -> bool:
        return bool(self.hard_issues)


@dataclass(frozen=True)
class BufferedSceneExecutionResult:
    scene_id: str
    scene_trace_id: str
    events: tuple[dict[str, str], ...]
    qa_result: dict[str, Any]
    retries_used: int
    word_count: int
    continuity_tokens: tuple[str, ...]


ARTIFACT_POLICIES: dict[str, ArtifactPlanningPolicy] = {
    "storyboard_grid": ArtifactPlanningPolicy(
        artifact_type="storyboard_grid",
        planning_mode="sequential",
        script_shape="sequential_storyboard",
        scene_budget=SceneBudgetPolicy(default=4, minimum=3, maximum=8, derive_from_duration=True, expansion_rule="normal"),
        salience_pass="FULL",
        forward_pull_pass="FULL",
        planner_focus=("progression", "scene turns", "coverage", "payoff"),
        generator_notes=("Multi-scene continuity matters.", "Voiceover pacing can drive scene order."),
    ),
    "comparison_one_pager": ArtifactPlanningPolicy(
        artifact_type="comparison_one_pager",
        planning_mode="static",
        script_shape="one_pager_board",
        scene_budget=SceneBudgetPolicy(default=1, minimum=1, maximum=1, derive_from_duration=False, expansion_rule="never"),
        salience_pass="FULL",
        forward_pull_pass="LITE",
        planner_focus=("hook", "modular information hierarchy", "evidence grouping", "synthesis", "dense readable composition"),
        generator_notes=("One canvas only.", "Convert beats into modules, not scenes.", "Do not turn this into a cinematic progression."),
    ),
    "slide_thumbnail": ArtifactPlanningPolicy(
        artifact_type="slide_thumbnail",
        planning_mode="static",
        script_shape="thumbnail_focus",
        scene_budget=SceneBudgetPolicy(default=1, minimum=1, maximum=2, derive_from_duration=False, expansion_rule="variant_only"),
        salience_pass="LITE",
        forward_pull_pass="FULL",
        planner_focus=("hook", "hero frame", "crop safety", "headline area"),
        generator_notes=("Usually one hero frame.", "Second scene is allowed only as a variant."),
    ),
    "technical_infographic": ArtifactPlanningPolicy(
        artifact_type="technical_infographic",
        planning_mode="static",
        script_shape="technical_infographic",
        scene_budget=SceneBudgetPolicy(default=1, minimum=1, maximum=2, derive_from_duration=False, expansion_rule="overview_plus_detail_only"),
        salience_pass="FULL",
        forward_pull_pass="OFF",
        planner_focus=("mechanism clarity", "module grouping", "factual hierarchy"),
        generator_notes=("Prioritize explanatory structure over suspense.", "Two scenes only when overview plus detail is truly needed."),
    ),
    "process_diagram": ArtifactPlanningPolicy(
        artifact_type="process_diagram",
        planning_mode="static",
        script_shape="process_map",
        scene_budget=SceneBudgetPolicy(default=1, minimum=1, maximum=2, derive_from_duration=False, expansion_rule="overview_plus_detail_only"),
        salience_pass="FULL",
        forward_pull_pass="OFF",
        planner_focus=("flow order", "state transitions", "decision points"),
        generator_notes=("Single composed flow is the default.", "Use a second scene only for zoomed detail."),
    ),
}


class GeminiStoryAgent:
    def __init__(self) -> None:
        self.client = get_gemini_client()

    @staticmethod
    def _load_schema_text(filename: str) -> str:
        return (SCHEMAS_DIR / filename).read_text(encoding="utf-8")

    @staticmethod
    def _build_signal_extraction_prompt(
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
            if source_inventory_text.strip()
            else ""
        )
        transcript_only_guardrail = (
            "11) This source path is transcript-backed video without direct frame access.\n"
            "12) If the transcript says 'this chart', 'as you can see', or similar, do not invent exact on-screen visuals. "
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

        # v2 prompt: still single-pass, but with stronger grounding and salience rules.
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

    @staticmethod
    def _source_manifest_for_extraction(
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> SourceManifestSchema | None:
        if source_manifest is None:
            return None
        if isinstance(source_manifest, SourceManifestSchema):
            return source_manifest
        if isinstance(source_manifest, dict):
            try:
                return SourceManifestSchema.model_validate(source_manifest)
            except Exception:
                return None
        return None

    @staticmethod
    def _source_manifest_summary(source_manifest: SourceManifestSchema | dict[str, Any] | None) -> str:
        manifest = GeminiStoryAgent._source_manifest_for_extraction(source_manifest)
        if manifest is None or not manifest.assets:
            return ""

        lines: list[str] = []
        for asset in manifest.assets[:8]:
            parts = [asset.modality]
            if asset.title:
                parts.append(asset.title)
            if asset.page_index is not None:
                parts.append(f"page {asset.page_index}")
            if asset.mime_type:
                parts.append(asset.mime_type)
            if isinstance(asset.metadata, dict):
                original_name = str(asset.metadata.get("original_filename", "")).strip()
                if original_name and original_name != asset.title:
                    parts.append(f"original file: {original_name}")
            lines.append(f"- {asset.asset_id}: {' | '.join(parts)}")
        return "\n".join(lines)

    @staticmethod
    def _is_youtube_video_asset(asset: SourceAssetSchema) -> bool:
        if asset.modality != "video":
            return False
        raw_uri = str(asset.uri or "").strip()
        if not raw_uri:
            return False
        try:
            host = urlparse(raw_uri).netloc.lower()
        except Exception:
            return False
        return any(domain in host for domain in ("youtube.com", "youtu.be", "youtube-nocookie.com"))

    @staticmethod
    def _transcript_only_video_mode(source_manifest: SourceManifestSchema | dict[str, Any] | None) -> bool:
        manifest = GeminiStoryAgent._source_manifest_for_extraction(source_manifest)
        if manifest is None or not manifest.assets:
            return False
        return any(GeminiStoryAgent._is_youtube_video_asset(asset) for asset in manifest.assets)

    @staticmethod
    def _transcript_needs_normalization(text: str) -> bool:
        sample = str(text or "").strip()
        if len(sample) < 120:
            return False
        punctuation_count = sum(sample.count(mark) for mark in ".?!")
        line_break_count = sample.count("\n")
        long_run = len(max(sample.splitlines() or [sample], key=len, default=""))
        return punctuation_count <= max(1, len(sample) // 500) or (line_break_count <= 1 and long_run > 220)

    @staticmethod
    def _build_transcript_normalization_prompt(
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

    async def _normalize_transcript_source_text(
        self,
        *,
        source_text: str,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> tuple[str, str]:
        inventory_text = self._source_manifest_summary(source_manifest)
        prompt = self._build_transcript_normalization_prompt(
            transcript_text=source_text,
            source_inventory_text=inventory_text,
        )
        response = await self.client.aio.models.generate_content(
            model=self._signal_source_text_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        payload = self._parse_json_object_response(response.text)
        normalized_text = str(payload.get("normalized_source_text", "")).strip() or source_text
        origin = str(payload.get("source_text_origin", "")).strip() or (
            "youtube_transcript_normalized"
            if self._transcript_only_video_mode(source_manifest)
            else "video_transcript_normalized"
        )
        return normalized_text[:20000], origin

    @staticmethod
    def _signal_structural_model() -> str:
        return os.getenv("EXPLAINFLOW_SIGNAL_STRUCTURAL_MODEL", SIGNAL_STRUCTURAL_MODEL_DEFAULT).strip() or SIGNAL_STRUCTURAL_MODEL_DEFAULT

    @staticmethod
    def _signal_creative_model() -> str:
        return os.getenv("EXPLAINFLOW_SIGNAL_CREATIVE_MODEL", SIGNAL_CREATIVE_MODEL_DEFAULT).strip() or SIGNAL_CREATIVE_MODEL_DEFAULT

    @staticmethod
    def _signal_source_text_model() -> str:
        return os.getenv("EXPLAINFLOW_SIGNAL_SOURCE_TEXT_MODEL", SIGNAL_SOURCE_TEXT_MODEL_DEFAULT).strip() or SIGNAL_SOURCE_TEXT_MODEL_DEFAULT

    @staticmethod
    def _planner_precompute_model() -> str:
        return os.getenv("EXPLAINFLOW_PLANNER_PRECOMPUTE_MODEL", PLANNER_PRECOMPUTE_MODEL_DEFAULT).strip() or PLANNER_PRECOMPUTE_MODEL_DEFAULT

    @staticmethod
    def _quick_artifact_model() -> str:
        return os.getenv("EXPLAINFLOW_QUICK_ARTIFACT_MODEL", QUICK_ARTIFACT_MODEL_DEFAULT).strip() or QUICK_ARTIFACT_MODEL_DEFAULT

    @staticmethod
    def _advanced_scene_concurrency() -> int:
        raw_value = os.getenv("EXPLAINFLOW_ADVANCED_SCENE_CONCURRENCY", str(ADVANCED_SCENE_CONCURRENCY_DEFAULT)).strip()
        try:
            parsed = int(raw_value)
        except Exception:
            parsed = ADVANCED_SCENE_CONCURRENCY_DEFAULT
        return max(1, min(parsed, 4))

    async def _build_asset_augmented_contents(
        self,
        *,
        prompt: str,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        allowed_modalities: set[str] | None = None,
        uploaded_assets: UploadedSourceAssets | None = None,
    ) -> tuple[str | list[Any], list[str], int]:
        if uploaded_assets is not None:
            if uploaded_assets.count == 0:
                return prompt, list(uploaded_assets.file_names), 0
            return [prompt, *uploaded_assets.parts], list(uploaded_assets.file_names), uploaded_assets.count

        uploaded_assets = await self._upload_source_asset_parts(
            source_manifest=source_manifest,
            allowed_modalities=allowed_modalities,
        )
        if uploaded_assets.count == 0:
            return prompt, list(uploaded_assets.file_names), 0
        return [prompt, *uploaded_assets.parts], list(uploaded_assets.file_names), uploaded_assets.count

    @staticmethod
    def _parse_json_object_response(response_text: str) -> dict[str, Any]:
        payload: Any = json.loads(response_text)
        for _ in range(2):
            if isinstance(payload, dict):
                return payload
            if isinstance(payload, str):
                payload = json.loads(payload)
                continue
            break
        raise ValueError("Model response was not a JSON object.")

    async def _upload_source_asset_parts(
        self,
        *,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        allowed_modalities: set[str] | None = None,
    ) -> UploadedSourceAssets:
        manifest = self._source_manifest_for_extraction(source_manifest)
        if manifest is None or not manifest.assets:
            return UploadedSourceAssets(parts=(), file_names=(), count=0)

        parts: list[Any] = []
        uploaded_file_names: list[str] = []
        uploaded_count = 0
        modal_allowlist = allowed_modalities or {"audio", "image", "pdf_page"}

        for asset in manifest.assets[:6]:
            if asset.modality not in modal_allowlist:
                continue

            local_path = asset_path_from_reference(asset.uri)
            if local_path is None:
                continue

            try:
                uploaded = await self.client.aio.files.upload(
                    file=str(local_path),
                    config=types.UploadFileConfig(
                        display_name=asset.title or local_path.name,
                        mime_type=asset.mime_type,
                    ),
                )
            except Exception as exc:
                print(f"Source upload failed for {asset.asset_id}: {exc}")
                continue

            upload_name = getattr(uploaded, "name", None)
            upload_uri = getattr(uploaded, "uri", None)
            upload_mime = getattr(uploaded, "mime_type", None) or asset.mime_type
            if isinstance(upload_name, str) and upload_name:
                uploaded_file_names.append(upload_name)
            if not isinstance(upload_uri, str) or not upload_uri:
                continue

            parts.append(
                types.Part.from_uri(
                    file_uri=upload_uri,
                    mime_type=upload_mime or "application/octet-stream",
                )
            )
            uploaded_count += 1

        return UploadedSourceAssets(
            parts=tuple(parts),
            file_names=tuple(uploaded_file_names),
            count=uploaded_count,
        )

    async def _build_signal_extraction_contents(
        self,
        *,
        document_text: str,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        schema_text: str,
        version: str,
        uploaded_assets: UploadedSourceAssets | None = None,
    ) -> tuple[str | list[Any], list[str], int]:
        inventory_text = self._source_manifest_summary(source_manifest)
        prompt = self._build_signal_extraction_prompt(
            document_text=document_text,
            schema_text=schema_text,
            version=version,
            source_inventory_text=inventory_text,
            transcript_only_video=self._transcript_only_video_mode(source_manifest),
        )
        return await self._build_asset_augmented_contents(
            prompt=prompt,
            source_manifest=source_manifest,
            uploaded_assets=uploaded_assets,
        )

    @staticmethod
    def _build_source_text_recovery_prompt(
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

    @staticmethod
    def _build_structural_signal_prompt(
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
            f"{transcript_guardrail}"
            "SOURCE:\n"
            f"{source_body}"
            f"{inventory_block}\n"
        )

    @staticmethod
    def _build_creative_signal_prompt(
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

    @staticmethod
    def _build_fallback_narrative_beats(
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

    @staticmethod
    def _build_fallback_visual_candidates(
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

    @staticmethod
    def _merge_signal_extraction_passes(
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
            beats = GeminiStoryAgent._build_fallback_narrative_beats(structural_signal=structural_signal)

        visual_candidates: list[dict[str, Any]] = []
        valid_structures = {"flowchart", "timeline", "comparison", "matrix", "process", "architecture", "concept_map", "table"}
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
            visual_candidates = GeminiStoryAgent._build_fallback_visual_candidates(structural_signal=structural_signal)

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

    async def _recover_normalized_source_text(
        self,
        *,
        input_text: str,
        normalized_source_text: str,
        source_text_origin: str | None,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        uploaded_assets: UploadedSourceAssets | None = None,
    ) -> tuple[str, str | None]:
        provided_text = str(input_text or "").strip()
        if provided_text:
            return provided_text, "pasted_text"

        supplied_normalized = str(normalized_source_text or "").strip()
        if supplied_normalized:
            return supplied_normalized, (source_text_origin or "normalized_source_text")

        manifest_text, manifest_origin = best_effort_manifest_text(source_manifest)
        if manifest_text:
            return manifest_text[:20000], manifest_origin

        inventory_text = self._source_manifest_summary(source_manifest)
        prompt = self._build_source_text_recovery_prompt(source_inventory_text=inventory_text)
        contents, _, uploaded_count = await self._build_asset_augmented_contents(
            prompt=prompt,
            source_manifest=source_manifest,
            uploaded_assets=uploaded_assets,
        )
        if uploaded_count == 0:
            return "", None

        response = await self.client.aio.models.generate_content(
            model=self._signal_source_text_model(),
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        payload = self._parse_json_object_response(response.text)
        recovered_text = str(payload.get("normalized_source_text", "")).strip()
        recovered_origin = str(payload.get("source_text_origin", "")).strip() or "gemini_asset_text"
        return recovered_text[:20000], recovered_origin

    async def _extract_signal_structural(
        self,
        *,
        normalized_source_text: str,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        uploaded_assets: UploadedSourceAssets | None = None,
    ) -> dict[str, Any]:
        inventory_text = self._source_manifest_summary(source_manifest)
        prompt = self._build_structural_signal_prompt(
            document_text=normalized_source_text,
            source_inventory_text=inventory_text,
            transcript_only_video=self._transcript_only_video_mode(source_manifest),
        )
        contents, _, _ = await self._build_asset_augmented_contents(
            prompt=prompt,
            source_manifest=source_manifest,
            uploaded_assets=uploaded_assets,
        )
        response = await self.client.aio.models.generate_content(
            model=self._signal_structural_model(),
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        payload = self._parse_json_object_response(response.text)
        if "narrative_beats" in payload:
            payload.pop("narrative_beats", None)
        if "visual_candidates" in payload:
            payload.pop("visual_candidates", None)
        return payload

    async def _extract_signal_creative(
        self,
        *,
        normalized_source_text: str,
        structural_signal: dict[str, Any],
        source_manifest: SourceManifestSchema | dict[str, Any] | None = None,
        fallback_to_pro: bool = True,
    ) -> dict[str, Any]:
        prompt = self._build_creative_signal_prompt(
            document_text=normalized_source_text,
            structural_signal=structural_signal,
            transcript_only_video=self._transcript_only_video_mode(source_manifest),
        )
        models_to_try = [self._signal_creative_model()]
        structural_model = self._signal_structural_model()
        if fallback_to_pro and structural_model not in models_to_try:
            models_to_try.append(structural_model)

        last_error: Exception | None = None
        for model_name in models_to_try:
            try:
                response = await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.4,
                        response_mime_type="application/json",
                    ),
                )
                return self._parse_json_object_response(response.text)
            except Exception as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise ValueError("Creative signal extraction failed without a model response.")

    @staticmethod
    def _style_guide_for_mode(visual_mode: str) -> str:
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

    @staticmethod
    def _is_resource_exhausted(exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "resource_exhausted" in message
            or "quota exceeded" in message
            or "429" in message
            or "rate limit" in message
        )

    @staticmethod
    def _is_daily_quota_exhausted(exc: Exception) -> bool:
        message = str(exc).lower()
        return "perday" in message or "per-day" in message or "requestsperday" in message

    @staticmethod
    def _extract_retry_delay_seconds(exc: Exception, default_seconds: float = 5.0) -> float:
        message = str(exc)
        retry_in_match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
        if retry_in_match:
            return max(1.0, min(float(retry_in_match.group(1)), 30.0))

        retry_delay_match = re.search(r"retryDelay': '([0-9]+)s'", message)
        if retry_delay_match:
            return max(1.0, min(float(retry_delay_match.group(1)), 30.0))

        return default_seconds

    @staticmethod
    def _friendly_quota_error_message() -> str:
        return (
            "Gemini generation is temporarily unavailable due to quota or rate limits "
            "(RESOURCE_EXHAUSTED). Wait ~30-60 seconds and retry, or use a billed API key/project."
        )

    @staticmethod
    def _new_run_id(prefix: str) -> str:
        return f"{prefix}-{int(time.time())}-{uuid4().hex[:8]}"

    @staticmethod
    def _resolve_artifact_scope(
        requested_scope: list[ArtifactName] | None,
        render_profile: dict[str, Any] | None = None,
        default_scope: list[ArtifactName] | None = None,
    ) -> list[ArtifactName]:
        if requested_scope:
            return requested_scope

        profile = render_profile or {}
        output_controls = profile.get("output_controls", {})
        raw_artifacts = output_controls.get("artifacts", [])
        if isinstance(raw_artifacts, list):
            normalized = [
                item
                for item in raw_artifacts
                if item in {"thumbnail", "story_cards", "storyboard", "voiceover", "social_caption"}
            ]
            if normalized:
                return normalized  # type: ignore[return-value]

        return default_scope or ["story_cards", "voiceover"]

    @staticmethod
    def _claim_traceability_summary(
        *,
        claim_ids: list[str],
        scene_claim_map: dict[str, list[str]],
        evidence_ids: list[str] | None = None,
        scene_evidence_map: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        referenced_claims = sorted(
            {
                claim_ref
                for scene_claims in scene_claim_map.values()
                for claim_ref in scene_claims
                if claim_ref
            }
        )
        unmapped_claims = [claim_id for claim_id in claim_ids if claim_id not in referenced_claims]
        payload = {
            "claims_total": len(claim_ids),
            "claims_referenced": len(referenced_claims),
            "unmapped_claims": unmapped_claims,
            "scene_claim_map": scene_claim_map,
        }
        if evidence_ids is not None and scene_evidence_map is not None:
            referenced_evidence = sorted(
                {
                    evidence_ref
                    for evidence_refs in scene_evidence_map.values()
                    for evidence_ref in evidence_refs
                    if evidence_ref
                }
            )
            payload["evidence_total"] = len(evidence_ids)
            payload["evidence_referenced"] = len(referenced_evidence)
            payload["unmapped_evidence"] = [evidence_id for evidence_id in evidence_ids if evidence_id not in referenced_evidence]
            payload["scene_evidence_map"] = scene_evidence_map
        return payload

    @staticmethod
    def _resolve_planner_artifact_type(
        *,
        render_profile: dict[str, Any] | None = None,
        artifact_scope: list[ArtifactName] | None = None,
    ) -> str:
        profile = render_profile or {}
        artifact_type = str(profile.get("artifact_type", "")).strip().lower()
        if artifact_type in ARTIFACT_POLICIES:
            return artifact_type

        scope = set(artifact_scope or [])
        if "storyboard" in scope:
            return "storyboard_grid"
        if "thumbnail" in scope:
            return "slide_thumbnail"
        if scope == {"story_cards", "social_caption"}:
            return "comparison_one_pager"
        return DEFAULT_PLANNER_ARTIFACT_TYPE

    @staticmethod
    def _resolve_artifact_policy(
        *,
        render_profile: dict[str, Any] | None = None,
        artifact_scope: list[ArtifactName] | None = None,
    ) -> ArtifactPlanningPolicy:
        artifact_type = GeminiStoryAgent._resolve_planner_artifact_type(
            render_profile=render_profile,
            artifact_scope=artifact_scope,
        )
        return ARTIFACT_POLICIES.get(artifact_type, ARTIFACT_POLICIES[DEFAULT_PLANNER_ARTIFACT_TYPE])

    @staticmethod
    def _source_asset_lookup(
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> dict[str, SourceAssetSchema]:
        if source_manifest is None:
            return {}

        manifest: SourceManifestSchema
        if isinstance(source_manifest, SourceManifestSchema):
            manifest = source_manifest
        elif isinstance(source_manifest, dict):
            try:
                manifest = SourceManifestSchema.model_validate(source_manifest)
            except Exception:
                return {}
        else:
            return {}

        return {
            asset.asset_id: asset
            for asset in manifest.assets
            if asset.asset_id and asset.modality in {"audio", "video", "image", "pdf_page"}
        }

    @staticmethod
    def _asset_duration_ms(asset: SourceAssetSchema | None) -> int | None:
        if asset is None:
            return None
        if isinstance(asset.duration_ms, int) and asset.duration_ms >= 0:
            return asset.duration_ms
        if isinstance(asset.metadata, dict):
            raw_duration = asset.metadata.get("duration_ms")
            if isinstance(raw_duration, (int, float)) and raw_duration >= 0:
                return int(raw_duration)
        return None

    @staticmethod
    def _coerce_timecode_ms(raw_value: Any, *, asset_duration_ms: int | None = None) -> int | None:
        if raw_value is None:
            return None

        if isinstance(raw_value, (int, float)):
            numeric_value = max(0, int(raw_value))
        else:
            text = str(raw_value).strip().lower()
            if not text:
                return None

            if re.fullmatch(r"\d+(?:\.\d+)?ms", text):
                return max(0, int(float(text[:-2])))
            if re.fullmatch(r"\d+(?:\.\d+)?s", text):
                return max(0, int(float(text[:-1]) * 1000))
            if ":" in text:
                parts = [part.strip() for part in text.split(":") if part.strip()]
                if not parts:
                    return None
                try:
                    numeric_parts = [float(part) for part in parts]
                except ValueError:
                    return None
                seconds = 0.0
                for part in numeric_parts:
                    seconds = seconds * 60 + part
                return max(0, int(seconds * 1000))
            if re.fullmatch(r"\d+(?:\.\d+)?", text):
                numeric_value = max(0, int(float(text)))
            else:
                return None

        if asset_duration_ms is not None and numeric_value > 0 and numeric_value <= (asset_duration_ms // 1000) + 2:
            return numeric_value * 1000
        return numeric_value

    @staticmethod
    def _coerce_evidence_time_range_ms(
        snippet: dict[str, Any],
        *,
        modality: str | None = None,
        asset_duration_ms: int | None = None,
    ) -> tuple[int | None, int | None, bool]:
        raw_start = snippet.get("start_ms", snippet.get("start_time"))
        raw_end = snippet.get("end_ms", snippet.get("end_time"))
        raw_timestamp = snippet.get("timestamp")
        timing_inferred = False

        if isinstance(raw_start, str) and raw_end is None:
            range_match = re.split(r"\s*(?:-|–|—|to)\s*", raw_start, maxsplit=1)
            if len(range_match) == 2:
                raw_start, raw_end = range_match[0], range_match[1]

        if raw_start is None and raw_end is None and isinstance(raw_timestamp, str):
            range_match = re.split(r"\s*(?:-|–|—|to)\s*", raw_timestamp, maxsplit=1)
            if len(range_match) == 2:
                raw_start, raw_end = range_match[0], range_match[1]
            else:
                raw_start = raw_timestamp

        start_ms = GeminiStoryAgent._coerce_timecode_ms(raw_start, asset_duration_ms=asset_duration_ms)
        end_ms = GeminiStoryAgent._coerce_timecode_ms(raw_end, asset_duration_ms=asset_duration_ms)
        if start_ms is not None and end_ms is not None and end_ms < start_ms:
            start_ms, end_ms = end_ms, start_ms
        if start_ms is not None and end_ms is None and modality in {"audio", "video"}:
            inferred_end = start_ms + 15_000
            if asset_duration_ms is not None:
                inferred_end = min(inferred_end, asset_duration_ms)
            if inferred_end > start_ms:
                end_ms = inferred_end
                timing_inferred = True
        return start_ms, end_ms, timing_inferred

    @staticmethod
    def _structured_evidence_refs(
        content_signal: dict[str, Any],
        source_manifest: SourceManifestSchema | dict[str, Any] | None = None,
    ) -> tuple[dict[str, list[EvidenceRefSchema]], dict[str, EvidenceRefSchema], list[str]]:
        by_claim: dict[str, list[EvidenceRefSchema]] = {}
        by_id: dict[str, EvidenceRefSchema] = {}
        evidence_ids: list[str] = []
        asset_lookup = GeminiStoryAgent._source_asset_lookup(source_manifest)

        key_claims = content_signal.get("key_claims", [])
        if not isinstance(key_claims, list):
            return by_claim, by_id, evidence_ids

        for claim in key_claims:
            if not isinstance(claim, dict):
                continue
            claim_id = str(claim.get("claim_id", "")).strip()
            if not claim_id:
                continue
            snippets = claim.get("evidence_snippets", [])
            if not isinstance(snippets, list):
                continue

            for index, snippet in enumerate(snippets, start=1):
                if not isinstance(snippet, dict):
                    continue
                modality = str(
                    snippet.get("modality")
                    or snippet.get("type")
                    or ""
                ).strip().lower()
                asset_id = str(snippet.get("asset_id", "")).strip()
                if modality not in {"text", "audio", "video", "image", "pdf_page"} or not asset_id:
                    continue

                evidence_id = str(snippet.get("evidence_id", "")).strip() or f"{claim_id}-e{index}"
                asset_duration_ms = GeminiStoryAgent._asset_duration_ms(asset_lookup.get(asset_id))
                start_ms, end_ms, timing_inferred = GeminiStoryAgent._coerce_evidence_time_range_ms(
                    snippet,
                    modality=modality,
                    asset_duration_ms=asset_duration_ms,
                )
                try:
                    evidence = EvidenceRefSchema(
                        evidence_id=evidence_id,
                        asset_id=asset_id,
                        modality=modality,  # type: ignore[arg-type]
                        quote_text=str(snippet.get("quote_text", "")).strip() or None,
                        transcript_text=str(snippet.get("transcript_text", "")).strip() or None,
                        visual_context=str(snippet.get("visual_context", "")).strip() or None,
                        speaker=str(snippet.get("speaker", "")).strip() or None,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        timing_inferred=timing_inferred,
                        page_index=int(snippet["page_index"]) if snippet.get("page_index") is not None else None,
                        bbox_norm=[
                            float(value)
                            for value in snippet.get("bbox_norm", [])
                            if isinstance(value, (int, float))
                        ][:4]
                        or None,
                        confidence=float(snippet["confidence"]) if snippet.get("confidence") is not None else None,
                    )
                except Exception:
                    continue

                by_claim.setdefault(claim_id, []).append(evidence)
                by_id[evidence.evidence_id] = evidence
                evidence_ids.append(evidence.evidence_id)

        return by_claim, by_id, evidence_ids

    @staticmethod
    def _evidence_summary_bits(evidence_items: list[Any]) -> list[str]:
        bits: list[str] = []
        for item in evidence_items[:2]:
            if isinstance(item, str) and item.strip():
                bits.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue

            modality = str(item.get("modality") or item.get("type") or "evidence").strip().lower() or "evidence"
            summary_parts = [modality]
            if modality in {"audio", "video"}:
                start_ms = item.get("start_ms")
                end_ms = item.get("end_ms")
                if isinstance(start_ms, (int, float)) and isinstance(end_ms, (int, float)):
                    summary_parts.append(f"{int(start_ms)}-{int(end_ms)}ms")
            if modality == "pdf_page" and item.get("page_index") is not None:
                summary_parts.append(f"page {int(item['page_index'])}")
            if modality in {"image", "pdf_page"} and isinstance(item.get("bbox_norm"), list) and len(item["bbox_norm"]) == 4:
                summary_parts.append("region crop")

            quote = str(
                item.get("quote_text")
                or item.get("transcript_text")
                or item.get("visual_context")
                or item.get("text")
                or item.get("citation")
                or ""
            ).strip()
            if quote:
                summary_parts.append(quote[:80])

            bits.append(" | ".join(summary_parts))
        return bits

    @staticmethod
    def _media_ref_for_evidence(
        *,
        claim_ref: str,
        evidence: EvidenceRefSchema,
    ) -> SourceMediaRefSchema | None:
        if evidence.modality not in {"audio", "video", "image", "pdf_page"}:
            return None

        if evidence.modality in {"audio", "video"}:
            usage = "proof_clip"
        else:
            usage = "region_crop" if evidence.bbox_norm else "callout"
        label = (
            evidence.quote_text
            or evidence.visual_context
            or evidence.transcript_text
            or f"Proof for {claim_ref}"
        )
        return SourceMediaRefSchema(
            asset_id=evidence.asset_id,
            modality=evidence.modality,  # type: ignore[arg-type]
            usage=usage,  # type: ignore[arg-type]
            claim_refs=[claim_ref],
            evidence_refs=[evidence.evidence_id],
            start_ms=evidence.start_ms,
            end_ms=evidence.end_ms,
            timing_inferred=evidence.timing_inferred,
            page_index=evidence.page_index,
            bbox_norm=evidence.bbox_norm,
            label=label[:96],
            quote_text=evidence.quote_text,
            visual_context=evidence.visual_context,
            muted=evidence.modality != "audio",
            loop=evidence.modality == "audio",
        )

    @staticmethod
    def _evidence_page_index(
        evidence: EvidenceRefSchema,
        asset: SourceAssetSchema | None = None,
    ) -> int | None:
        if evidence.page_index is not None:
            return evidence.page_index
        if asset is not None:
            return asset.page_index
        return None

    @staticmethod
    def _evidence_page_key(
        evidence: EvidenceRefSchema,
        asset: SourceAssetSchema | None = None,
    ) -> tuple[str, int | None]:
        return (evidence.asset_id, GeminiStoryAgent._evidence_page_index(evidence, asset))

    @staticmethod
    def _media_page_key(media: SourceMediaRefSchema) -> tuple[str, int | None]:
        return (media.asset_id, media.page_index)

    @staticmethod
    def _evidence_text_blob(evidence: EvidenceRefSchema) -> str:
        return " ".join(
            part.strip()
            for part in [
                evidence.quote_text or "",
                evidence.transcript_text or "",
                evidence.visual_context or "",
            ]
            if part and part.strip()
        ).lower()

    @staticmethod
    def _is_frontmatter_pdf_evidence(
        evidence: EvidenceRefSchema,
        asset: SourceAssetSchema | None = None,
    ) -> bool:
        if evidence.modality != "pdf_page":
            return False
        page_index = GeminiStoryAgent._evidence_page_index(evidence, asset)
        text_blob = GeminiStoryAgent._evidence_text_blob(evidence)
        if "abstract" in text_blob or "executive summary" in text_blob:
            return True
        return page_index == 1

    @staticmethod
    def _scene_is_opener_or_hook(
        scene: ScriptPackScene,
        scene_index: int,
    ) -> bool:
        if scene_index == 0:
            return True
        scene_role = (scene.scene_role or "").strip().lower()
        return scene_role in {"hook", "bait", "bait_hook", "setup"}

    @staticmethod
    def _sort_claim_evidence_for_scene(
        *,
        scene: ScriptPackScene,
        scene_index: int,
        claim_ref: str,
        evidence_items: list[EvidenceRefSchema],
        asset_lookup: dict[str, SourceAssetSchema],
        page_usage_counts: dict[tuple[str, int | None], int],
        evidence_usage_counts: dict[str, int],
        allow_frontmatter: bool,
    ) -> list[EvidenceRefSchema]:
        if not evidence_items:
            return []

        claim_has_non_frontmatter_media = any(
            evidence.asset_id in asset_lookup
            and not GeminiStoryAgent._is_frontmatter_pdf_evidence(
                evidence,
                asset_lookup.get(evidence.asset_id),
            )
            for evidence in evidence_items
            if evidence.modality in {"audio", "image", "pdf_page"}
        )

        filtered_items = [
            evidence
            for evidence in evidence_items
            if allow_frontmatter
            or not GeminiStoryAgent._is_frontmatter_pdf_evidence(
                evidence,
                asset_lookup.get(evidence.asset_id),
            )
            or not claim_has_non_frontmatter_media
        ]
        candidates = filtered_items or evidence_items

        def score(evidence: EvidenceRefSchema) -> float:
            asset = asset_lookup.get(evidence.asset_id)
            page_key = GeminiStoryAgent._evidence_page_key(evidence, asset)
            page_index = GeminiStoryAgent._evidence_page_index(evidence, asset)
            is_frontmatter = GeminiStoryAgent._is_frontmatter_pdf_evidence(evidence, asset)
            score_value = float(evidence.confidence or 0.5) * 10.0

            if evidence.modality == "audio":
                score_value += 16.0
            elif evidence.modality == "image":
                score_value += 18.0
            elif evidence.modality == "pdf_page":
                score_value += 14.0
            if evidence.bbox_norm:
                score_value += 22.0
            if evidence.quote_text or evidence.transcript_text:
                score_value += 5.0
            if evidence.visual_context:
                score_value += 3.0

            if page_index is not None and page_index > 1:
                score_value += 10.0
            if is_frontmatter:
                score_value += 20.0 if allow_frontmatter else -35.0

            score_value -= page_usage_counts.get(page_key, 0) * 18.0
            score_value -= evidence_usage_counts.get(evidence.evidence_id, 0) * 28.0
            score_value -= scene_index * 0.25
            return score_value

        return sorted(
            candidates,
            key=lambda evidence: (
                score(evidence),
                -(
                    GeminiStoryAgent._evidence_page_index(
                        evidence,
                        asset_lookup.get(evidence.asset_id),
                    )
                    or 0
                ),
            ),
            reverse=True,
        )

    @staticmethod
    def _enrich_script_pack_with_source_media(
        *,
        script_pack: ScriptPack,
        content_signal: dict[str, Any],
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> tuple[ScriptPack, dict[str, list[str]], list[str]]:
        asset_lookup = GeminiStoryAgent._source_asset_lookup(source_manifest)
        evidence_by_claim, _, evidence_ids = GeminiStoryAgent._structured_evidence_refs(
            content_signal,
            source_manifest,
        )
        if not evidence_by_claim or not asset_lookup:
            return script_pack, {scene.scene_id: list(scene.evidence_refs) for scene in script_pack.scenes}, evidence_ids

        enriched = script_pack.model_copy(deep=True)
        scene_evidence_map: dict[str, list[str]] = {}
        page_usage_counts: dict[tuple[str, int | None], int] = {}
        evidence_usage_counts: dict[str, int] = {}
        abstract_scene_claimed = False

        for scene_index, scene in enumerate(enriched.scenes):
            evidence_refs = list(scene.evidence_refs)
            source_media = list(scene.source_media)
            media_keys = {
                (
                    item.asset_id,
                    tuple(item.claim_refs),
                    tuple(item.evidence_refs),
                    item.start_ms,
                    item.end_ms,
                    item.page_index,
                    tuple(item.bbox_norm or []),
                )
                for item in source_media
            }
            allow_frontmatter = GeminiStoryAgent._scene_is_opener_or_hook(scene, scene_index) and not abstract_scene_claimed
            scene_uses_frontmatter = False

            for claim_ref in scene.claim_refs[:4]:
                claim_page_like_selected = False
                claim_audio_selected = False
                ranked_evidence = GeminiStoryAgent._sort_claim_evidence_for_scene(
                    scene=scene,
                    scene_index=scene_index,
                    claim_ref=claim_ref,
                    evidence_items=evidence_by_claim.get(claim_ref, []),
                    asset_lookup=asset_lookup,
                    page_usage_counts=page_usage_counts,
                    evidence_usage_counts=evidence_usage_counts,
                    allow_frontmatter=allow_frontmatter,
                )
                for evidence in ranked_evidence[:3]:
                    is_page_like = evidence.modality in {"image", "pdf_page"}
                    if is_page_like and claim_page_like_selected:
                        continue
                    if evidence.modality == "audio" and claim_audio_selected:
                        continue

                    if evidence.asset_id not in asset_lookup:
                        if evidence.evidence_id not in evidence_refs:
                            evidence_refs.append(evidence.evidence_id)
                        continue

                    media_ref = GeminiStoryAgent._media_ref_for_evidence(
                        claim_ref=claim_ref,
                        evidence=evidence,
                    )
                    if media_ref is None:
                        if evidence.evidence_id not in evidence_refs:
                            evidence_refs.append(evidence.evidence_id)
                        continue

                    media_key = (
                        media_ref.asset_id,
                        tuple(media_ref.claim_refs),
                        tuple(media_ref.evidence_refs),
                        media_ref.start_ms,
                        media_ref.end_ms,
                        media_ref.page_index,
                        tuple(media_ref.bbox_norm or []),
                    )
                    if media_key in media_keys:
                        continue
                    if evidence.evidence_id not in evidence_refs:
                        evidence_refs.append(evidence.evidence_id)
                    source_media.append(media_ref)
                    media_keys.add(media_key)
                    if is_page_like:
                        claim_page_like_selected = True
                    if evidence.modality == "audio":
                        claim_audio_selected = True
                    if GeminiStoryAgent._is_frontmatter_pdf_evidence(
                        evidence,
                        asset_lookup.get(evidence.asset_id),
                    ):
                        scene_uses_frontmatter = True
                    if len(source_media) >= 3:
                        break
                if len(source_media) >= 3:
                    break

            scene.evidence_refs = evidence_refs[:8]
            scene.source_media = source_media[:3]
            if scene.source_media and scene.render_strategy == "generated":
                scene.render_strategy = "hybrid"

            for module in scene.modules:
                module_evidence_refs = list(module.evidence_refs)
                module_source_media = list(module.source_media)
                for claim_ref in module.claim_refs[:3]:
                    for evidence in evidence_by_claim.get(claim_ref, [])[:2]:
                        if evidence.evidence_id not in module_evidence_refs:
                            module_evidence_refs.append(evidence.evidence_id)
                        media_ref = GeminiStoryAgent._media_ref_for_evidence(
                            claim_ref=claim_ref,
                            evidence=evidence,
                        )
                        if media_ref is not None and evidence.asset_id in asset_lookup:
                            module_source_media.append(media_ref)
                module.evidence_refs = module_evidence_refs[:6]
                module.source_media = module_source_media[:2]

            for evidence_id in scene.evidence_refs:
                evidence_usage_counts[evidence_id] = evidence_usage_counts.get(evidence_id, 0) + 1
            for media in scene.source_media:
                page_key = GeminiStoryAgent._media_page_key(media)
                page_usage_counts[page_key] = page_usage_counts.get(page_key, 0) + 1
            if scene_uses_frontmatter:
                abstract_scene_claimed = True
            scene_evidence_map[scene.scene_id] = list(scene.evidence_refs)

        return enriched, scene_evidence_map, evidence_ids

    @staticmethod
    def _resolve_source_media_payloads(
        *,
        request: Request,
        scene_id: str,
        source_media: list[SourceMediaRefSchema],
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        asset_lookup = GeminiStoryAgent._source_asset_lookup(source_manifest)
        payloads: list[dict[str, Any]] = []

        for index, media in enumerate(source_media, start=1):
            asset = asset_lookup.get(media.asset_id)
            if asset is None:
                continue

            original_url = public_asset_url(request, asset.uri)
            if not original_url:
                continue

            resolved_url = original_url
            if media.modality in {"image", "pdf_page"} and media.bbox_norm:
                try:
                    resolved_url = crop_source_region_and_get_url(
                        request=request,
                        scene_id=f"{scene_id}-proof-{index}",
                        source_ref=asset.uri or original_url,
                        bbox_norm=media.bbox_norm,
                        prefix="source_media_crop",
                    )
                except Exception:
                    resolved_url = original_url

            payloads.append(
                {
                    "scene_id": scene_id,
                    "asset_id": media.asset_id,
                    "modality": media.modality,
                    "usage": media.usage,
                    "url": resolved_url,
                    "original_url": original_url,
                    "start_ms": media.start_ms,
                    "end_ms": media.end_ms,
                    "page_index": media.page_index if media.page_index is not None else asset.page_index,
                    "bbox_norm": media.bbox_norm,
                    "claim_refs": list(media.claim_refs),
                    "evidence_refs": list(media.evidence_refs),
                    "label": media.label or asset.title,
                    "quote_text": media.quote_text,
                    "visual_context": media.visual_context,
                    "speaker": asset.metadata.get("speaker") if isinstance(asset.metadata, dict) else None,
                    "loop": media.loop,
                    "muted": media.muted,
                }
            )
            payload = payloads[-1]

            if media.modality == "pdf_page":
                proof_locator = resolve_pdf_proof_locator(
                    asset_ref=asset.uri or original_url,
                    page_index=payload["page_index"],
                    quote_text=media.quote_text,
                    transcript_text=None,
                    visual_context=media.visual_context,
                )
                if proof_locator is not None:
                    payload.update(proof_locator)

        return payloads

    @staticmethod
    def _planner_source_text(
        *,
        source_text: str,
        normalized_source_text: str = "",
        content_signal: dict[str, Any],
    ) -> str:
        if isinstance(source_text, str) and source_text.strip():
            return source_text.strip()[:12000]
        if isinstance(normalized_source_text, str) and normalized_source_text.strip():
            return normalized_source_text.strip()[:12000]

        sections: list[str] = []
        thesis = content_signal.get("thesis", {})
        if isinstance(thesis, dict):
            one_liner = str(thesis.get("one_liner", "")).strip()
            if one_liner:
                sections.append(f"THESIS: {one_liner}")

        key_claims = content_signal.get("key_claims", [])
        if isinstance(key_claims, list) and key_claims:
            sections.append("KEY CLAIMS:")
            for claim in key_claims[:10]:
                if not isinstance(claim, dict):
                    continue
                claim_text = str(claim.get("claim_text", "")).strip()
                evidence = claim.get("evidence_snippets", [])
                evidence_bits = GeminiStoryAgent._evidence_summary_bits(evidence if isinstance(evidence, list) else [])
                line = claim_text
                if evidence_bits:
                    line += f" | evidence: {' ; '.join(evidence_bits)}"
                if line:
                    sections.append(f"- {line}")

        beats = content_signal.get("narrative_beats", [])
        if isinstance(beats, list) and beats:
            sections.append("NARRATIVE BEATS:")
            for beat in beats[:6]:
                if not isinstance(beat, dict):
                    continue
                message = str(beat.get("message", "")).strip()
                role = str(beat.get("role", "")).strip()
                text = f"{role}: {message}".strip(": ")
                if text:
                    sections.append(f"- {text}")

        return "\n".join(sections)[:12000]

    @staticmethod
    def _normalize_candidate_text(raw_value: Any) -> str:
        return re.sub(r"\s+", " ", str(raw_value or "").strip())

    @staticmethod
    def _salience_candidates(
        *,
        content_signal: dict[str, Any],
        mode: str,
        planning_mode: str,
    ) -> list[dict[str, str]]:
        key_claims = content_signal.get("key_claims", [])
        beats = content_signal.get("narrative_beats", [])
        candidates: list[dict[str, str]] = []

        if isinstance(key_claims, list):
            for index, claim in enumerate(key_claims, start=1):
                if not isinstance(claim, dict):
                    continue
                content = GeminiStoryAgent._normalize_candidate_text(
                    claim.get("claim_text") or claim.get("content") or claim.get("summary")
                )
                if not content:
                    continue
                candidate_id = str(claim.get("claim_id", "")).strip() or f"claim-{index}"
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_type": "key_claim",
                        "content": content,
                    }
                )

        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for candidate in candidates:
            dedupe_key = candidate["content"].lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deduped.append(candidate)

        if mode == "LITE":
            return deduped[:6]

        if planning_mode == "sequential" and isinstance(beats, list):
            for index, beat in enumerate(beats[:4], start=1):
                if not isinstance(beat, dict):
                    continue
                content = GeminiStoryAgent._normalize_candidate_text(
                    beat.get("message") or beat.get("summary") or beat.get("title")
                )
                if not content:
                    continue
                dedupe_key = content.lower()
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                candidate_id = str(beat.get("beat_id", "")).strip() or f"beat-{index}"
                deduped.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_type": "narrative_beat",
                        "content": content,
                    }
                )

        return deduped

    @staticmethod
    def _build_salience_prompt(
        *,
        source_text: str,
        candidates: list[dict[str, str]],
    ) -> str:
        return (
            "SYSTEM:\n"
            "You are evaluating narrative salience by counterfactual deletion.\n\n"
            "USER:\n"
            "For each candidate signal below, decide how much the story would change if it were removed.\n"
            "Return JSON only.\n\n"
            "Rules:\n"
            "- Use 3 ratings: CRITICAL / IMPORTANT / FLAVOUR.\n"
            "- CRITICAL means removing it breaks causal chain, stakes, or the central explanatory engine.\n"
            "- IMPORTANT means removing it weakens understanding, motivation, or foreshadowing.\n"
            "- FLAVOUR means mostly style, framing, or world texture.\n"
            "- Assume all other candidates remain fixed; evaluate deletion one item at a time.\n"
            "- If two candidates overlap heavily, mention overlap and avoid rating both CRITICAL.\n\n"
            "For each item provide:\n"
            "- candidate_id\n"
            "- candidate_type\n"
            "- content\n"
            "- rating\n"
            "- downstream_impact\n"
            "- evidence_quote (<=12 words)\n"
            "- overlap_with\n\n"
            f"SOURCE:\n{source_text}\n\n"
            f"CANDIDATE SIGNALS:\n{json.dumps(candidates, ensure_ascii=True)}"
        )

    @staticmethod
    def _build_forward_pull_prompt(
        *,
        source_text: str,
    ) -> str:
        return (
            "SYSTEM:\n"
            "You extract forward-pull narrative signals. Do not write prose.\n\n"
            "USER:\n"
            "Using the Bait-Hook-Threat-Reward-Payload lens, extract grounded signals from SOURCE.\n"
            "Definitions:\n"
            "- Bait: first anomaly or promise that grabs attention.\n"
            "- Hook: the main information gap or unresolved question.\n"
            "- Threat: explicit or implicit stakes if unresolved.\n"
            "- Reward: payoff signals such as reveal, reversal, decision, or relief.\n"
            "- Payload: the durable meaning, theme, plot engine, or transformation.\n\n"
            "Rules:\n"
            "- If the source is expository, map hook to the central explanatory gap.\n"
            "- If no real threat exists, return an empty threats list.\n"
            "- If no real reward exists, return an empty rewards list.\n"
            "- Keep everything source-grounded and concise.\n"
            "- Return JSON only.\n\n"
            f"SOURCE:\n{source_text}"
        )

    @staticmethod
    def _best_effort_salience_summary(salience: SalienceAssessmentSchema | None) -> str:
        if salience is None or not salience.items:
            return ""

        ranked = sorted(
            salience.items,
            key=lambda item: {"CRITICAL": 0, "IMPORTANT": 1, "FLAVOUR": 2}.get(item.rating, 3),
        )
        lines = ["SALIENCE MAP:"]
        for item in ranked:
            overlap = f" overlap={','.join(item.overlap_with)};" if item.overlap_with else ""
            lines.append(
                f"- {item.candidate_id} [{item.candidate_type}] {item.rating}: {item.content} "
                f"(impact: {item.downstream_impact}; evidence: {item.evidence_quote};{overlap})"
            )
        lines.append("Coverage rule: CRITICAL items are mandatory, IMPORTANT items should be covered if space allows, FLAVOUR items must not displace backbone material.")
        return "\n".join(lines)

    @staticmethod
    def _forward_pull_guidance(
        *,
        artifact_policy: ArtifactPlanningPolicy,
        forward_pull: ForwardPullSchema | None,
    ) -> str:
        if forward_pull is None:
            return ""

        lines: list[str] = []
        bait = forward_pull.bait
        hook = forward_pull.hook
        threats = forward_pull.threats
        rewards = forward_pull.rewards
        payloads = forward_pull.payloads

        if bait and bait.content:
            lines.append(f"Bait: {bait.content} | evidence: {bait.evidence_quote}")
        if hook and hook.question:
            lines.append(f"Hook: {hook.question} | evidence: {hook.evidence_quote}")

        if artifact_policy.artifact_type == "comparison_one_pager":
            if payloads:
                lines.append(
                    "Use mainly hook and payload in the header and synthesis framing: "
                    + "; ".join(payload.theme_or_engine for payload in payloads[:2])
                )
            if threats:
                grounded_threats = [threat.stake for threat in threats[:1] if threat.evidence_quote]
                if grounded_threats:
                    lines.append(f"Optional grounded stake framing: {'; '.join(grounded_threats)}")
        elif artifact_policy.artifact_type == "slide_thumbnail":
            if threats:
                lines.append("Use threat only if it sharpens the hook without fabricating drama.")
            if rewards:
                lines.append("Imply one payoff signal visually when it strengthens click-through.")
        elif artifact_policy.planning_mode == "sequential":
            if threats:
                lines.append(
                    "Threats: " + "; ".join(
                        f"{threat.stake} (risk: {threat.who_is_at_risk}; evidence: {threat.evidence_quote})"
                        for threat in threats[:3]
                    )
                )
            if rewards:
                lines.append(
                    "Rewards: " + "; ".join(
                        f"{reward.payoff_signal} (likely beat: {reward.likely_location}; evidence: {reward.evidence_quote})"
                        for reward in rewards[:3]
                    )
                )

        if payloads:
            lines.append(
                "Payloads: " + "; ".join(payload.theme_or_engine for payload in payloads[:3])
            )

        if not lines:
            return ""

        prefix = "FORWARD-PULL MAP:"
        if artifact_policy.forward_pull_pass == "LITE":
            lines.append("Consumption rule: use hook and payload first; ignore threat/reward if they do not fit the artifact.")
        else:
            lines.append("Consumption rule: use these signals to sharpen opener, tension, and payoff while staying source-grounded.")
        return "\n".join([prefix, *lines])

    @staticmethod
    def _matchable_text(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]+", " ", text.lower())).strip()

    @staticmethod
    def _text_matches_signal(text: str, signal_text: str) -> bool:
        normalized_text = GeminiStoryAgent._matchable_text(text)
        normalized_signal = GeminiStoryAgent._matchable_text(signal_text)
        if not normalized_text or not normalized_signal:
            return False
        if normalized_signal in normalized_text:
            return True

        anchor_terms = extract_anchor_terms(signal_text, limit=6)
        if not anchor_terms:
            anchor_terms = [token for token in normalized_signal.split() if len(token) >= 4][:6]
        if not anchor_terms:
            return False

        matches = sum(
            1 for term in anchor_terms if re.search(rf"\b{re.escape(term.lower())}\b", normalized_text)
        )
        threshold = 1 if len(anchor_terms) <= 2 else 2
        return matches >= threshold

    @staticmethod
    def _scene_blob(scene: ScriptPackScene) -> str:
        module_parts: list[str] = []
        for module in scene.modules:
            module_parts.extend(
                [
                    module.module_id,
                    module.label,
                    module.purpose,
                    module.content_type,
                    module.placement_hint or "",
                    *module.claim_refs,
                ]
            )

        parts = [
            scene.title,
            scene.scene_goal,
            scene.narration_focus,
            scene.visual_prompt,
            scene.scene_role or "",
            scene.composition_goal or "",
            scene.layout_template or "",
            scene.focal_subject or "",
            *scene.visual_hierarchy,
            *scene.comparison_axes,
            *scene.flow_steps,
            *module_parts,
            *scene.claim_refs,
        ]
        return " ".join(str(part).strip() for part in parts if str(part).strip())

    @staticmethod
    def _scene_covers_signal(
        scene: ScriptPackScene,
        *,
        candidate_id: str = "",
        signal_text: str = "",
        evidence_quote: str = "",
    ) -> bool:
        if candidate_id and candidate_id in scene.claim_refs:
            return True
        blob = GeminiStoryAgent._scene_blob(scene)
        if signal_text and GeminiStoryAgent._text_matches_signal(blob, signal_text):
            return True
        if evidence_quote and GeminiStoryAgent._text_matches_signal(blob, evidence_quote):
            return True
        return False

    @staticmethod
    def _prepend_guidance(text: str, addition: str) -> str:
        clean_addition = addition.strip().rstrip(".")
        clean_text = text.strip()
        if not clean_addition:
            return clean_text
        if GeminiStoryAgent._text_matches_signal(clean_text, clean_addition):
            return clean_text or clean_addition
        if not clean_text:
            return clean_addition
        return f"{clean_addition}. {clean_text}"

    @staticmethod
    def _append_guidance(text: str, addition: str) -> str:
        clean_addition = addition.strip().rstrip(".")
        clean_text = text.strip()
        if not clean_addition:
            return clean_text
        if GeminiStoryAgent._text_matches_signal(clean_text, clean_addition):
            return clean_text or clean_addition
        if not clean_text:
            return clean_addition
        return f"{clean_text} {clean_addition}."

    @staticmethod
    def _append_unique(items: list[str], value: str, *, limit: int | None = None) -> list[str]:
        clean_value = value.strip()
        next_items = [item for item in items if str(item).strip()]
        if not clean_value:
            return next_items
        if any(GeminiStoryAgent._text_matches_signal(item, clean_value) for item in next_items):
            return next_items[:limit] if limit else next_items
        next_items.append(clean_value)
        return next_items[:limit] if limit else next_items

    @staticmethod
    def _prepend_unique(items: list[str], value: str, *, limit: int | None = None) -> list[str]:
        clean_value = value.strip()
        filtered = [item for item in items if str(item).strip() and not GeminiStoryAgent._text_matches_signal(item, clean_value)]
        if clean_value:
            filtered.insert(0, clean_value)
        return filtered[:limit] if limit else filtered

    @staticmethod
    def _short_headline(text: str, *, max_words: int = 8, max_chars: int = 64) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        if not cleaned:
            return ""
        words = cleaned.split(" ")
        shortened = " ".join(words[:max_words]).strip()
        if len(shortened) > max_chars:
            shortened = shortened[:max_chars].rsplit(" ", 1)[0].strip() or shortened[:max_chars].strip()
        return shortened.rstrip(".,;:!?")

    @staticmethod
    def _critical_salience_items(salience: SalienceAssessmentSchema | None) -> list[SalienceAssessmentItem]:
        if salience is None:
            return []
        return [item for item in salience.items if item.rating == "CRITICAL"]

    @staticmethod
    def _important_salience_items(salience: SalienceAssessmentSchema | None) -> list[SalienceAssessmentItem]:
        if salience is None:
            return []
        return [item for item in salience.items if item.rating == "IMPORTANT"]

    @staticmethod
    def _build_enrichment_context(
        *,
        artifact_policy: ArtifactPlanningPolicy,
        thesis: str,
        audience_descriptor: str,
        claim_ids: list[str],
        scene_count: int,
        salience_assessment: SalienceAssessmentSchema | None,
        forward_pull: ForwardPullSchema | None,
    ) -> PlannerEnrichmentContext:
        return PlannerEnrichmentContext(
            artifact_policy=artifact_policy,
            thesis=thesis,
            audience_descriptor=audience_descriptor,
            claim_ids=tuple(claim_ids),
            scene_count=scene_count,
            salience_assessment=salience_assessment,
            forward_pull=forward_pull,
        )

    def _validate_script_pack_against_enrichments(
        self,
        *,
        script_pack: ScriptPack,
        context: PlannerEnrichmentContext,
    ) -> PlannerValidationReport:
        hard_issues: list[PlannerIssue] = []
        warnings: list[PlannerIssue] = []
        scenes = list(script_pack.scenes)
        if not scenes:
            return PlannerValidationReport(
                hard_issues=(PlannerIssue(severity="hard", code="no_scenes", message="Script pack produced no scenes."),),
                warnings=(),
            )

        for item in self._critical_salience_items(context.salience_assessment):
            covered = any(
                self._scene_covers_signal(
                    scene,
                    candidate_id=item.candidate_id,
                    signal_text=item.content,
                    evidence_quote=item.evidence_quote,
                )
                for scene in scenes
            )
            if not covered:
                hard_issues.append(
                    PlannerIssue(
                        severity="hard",
                        code="critical_missing",
                        message=f"Critical item {item.candidate_id} is not covered in the script pack.",
                        target=item.candidate_id,
                    )
                )

        for item in self._important_salience_items(context.salience_assessment):
            covered = any(
                self._scene_covers_signal(
                    scene,
                    candidate_id=item.candidate_id,
                    signal_text=item.content,
                    evidence_quote=item.evidence_quote,
                )
                for scene in scenes
            )
            if not covered:
                warnings.append(
                    PlannerIssue(
                        severity="warning",
                        code="important_missing",
                        message=f"Important item {item.candidate_id} is not explicitly covered.",
                        target=item.candidate_id,
                    )
                )

        forward_pull = context.forward_pull
        if forward_pull is None:
            return PlannerValidationReport(hard_issues=tuple(hard_issues), warnings=tuple(warnings))

        artifact_type = context.artifact_policy.artifact_type
        first_scene = scenes[0]
        last_scene = scenes[-1]

        if context.artifact_policy.planning_mode == "sequential":
            opener_signals = [
                forward_pull.bait.content if forward_pull.bait and forward_pull.bait.content else "",
                forward_pull.hook.question if forward_pull.hook and forward_pull.hook.question else "",
            ]
            if any(signal.strip() for signal in opener_signals):
                opener_ok = any(
                    self._scene_covers_signal(first_scene, signal_text=signal)
                    for signal in opener_signals
                    if signal.strip()
                )
                if not opener_ok:
                    hard_issues.append(
                        PlannerIssue(
                            severity="hard",
                            code="missing_opener_anchor",
                            message="First scene does not express the forward-pull bait or hook.",
                            scene_id=first_scene.scene_id,
                        )
                    )
            if first_scene.scene_role != "bait_hook":
                warnings.append(
                    PlannerIssue(
                        severity="warning",
                        code="opener_role_mismatch",
                        message="First scene should be tagged as bait_hook.",
                        scene_id=first_scene.scene_id,
                    )
                )

            closer_signals = [
                forward_pull.rewards[0].payoff_signal if forward_pull.rewards else "",
                forward_pull.payloads[0].theme_or_engine if forward_pull.payloads else "",
            ]
            if any(signal.strip() for signal in closer_signals):
                closer_ok = any(
                    self._scene_covers_signal(last_scene, signal_text=signal)
                    for signal in closer_signals
                    if signal.strip()
                )
                if not closer_ok:
                    hard_issues.append(
                        PlannerIssue(
                            severity="hard",
                            code="missing_closer_anchor",
                            message="Final scene does not express the reward or payload.",
                            scene_id=last_scene.scene_id,
                        )
                    )
            if last_scene.scene_role != "payoff":
                warnings.append(
                    PlannerIssue(
                        severity="warning",
                        code="closer_role_mismatch",
                        message="Final scene should be tagged as payoff.",
                        scene_id=last_scene.scene_id,
                    )
                )
        elif artifact_type == "comparison_one_pager":
            header_signals = [
                forward_pull.hook.question if forward_pull.hook and forward_pull.hook.question else "",
                forward_pull.payloads[0].theme_or_engine if forward_pull.payloads else "",
            ]
            if any(signal.strip() for signal in header_signals):
                header_ok = any(
                    self._scene_covers_signal(first_scene, signal_text=signal)
                    for signal in header_signals
                    if signal.strip()
                )
                if not header_ok:
                    hard_issues.append(
                        PlannerIssue(
                            severity="hard",
                            code="missing_comparison_header",
                            message="One-pager is missing hook or payload framing in its header or synthesis area.",
                            scene_id=first_scene.scene_id,
                        )
                    )
        elif artifact_type == "slide_thumbnail":
            anchor_signals = [
                forward_pull.hook.question if forward_pull.hook and forward_pull.hook.question else "",
                forward_pull.bait.content if forward_pull.bait and forward_pull.bait.content else "",
            ]
            if any(signal.strip() for signal in anchor_signals) and not any(
                self._scene_covers_signal(first_scene, signal_text=signal)
                for signal in anchor_signals
                if signal.strip()
            ):
                hard_issues.append(
                    PlannerIssue(
                        severity="hard",
                        code="missing_thumbnail_anchor",
                        message="Thumbnail scene does not express the dominant bait or hook.",
                        scene_id=first_scene.scene_id,
                    )
                )
            if len(first_scene.claim_refs) > 2:
                warnings.append(
                    PlannerIssue(
                        severity="warning",
                        code="thumbnail_diffuse",
                        message="Thumbnail should not spread across too many claim refs.",
                        scene_id=first_scene.scene_id,
                    )
                )

        return PlannerValidationReport(hard_issues=tuple(hard_issues), warnings=tuple(warnings))

    @staticmethod
    def _repair_target_scene(
        scenes: list[ScriptPackScene],
        *,
        artifact_type: str,
        index_hint: int,
    ) -> ScriptPackScene:
        if artifact_type in {"comparison_one_pager", "slide_thumbnail"} or len(scenes) == 1:
            return scenes[0]
        if artifact_type in {"technical_infographic", "process_diagram"}:
            return scenes[min(index_hint, len(scenes) - 1)]
        middle_scenes = scenes[1:-1] or scenes
        return min(middle_scenes, key=lambda scene: len(scene.claim_refs))

    def _repair_script_pack_from_enrichments(
        self,
        *,
        script_pack: ScriptPack,
        context: PlannerEnrichmentContext,
    ) -> ScriptPack:
        repaired = script_pack.model_copy(deep=True)
        scenes = list(repaired.scenes)
        if not scenes:
            return repaired

        artifact_type = context.artifact_policy.artifact_type

        for index, item in enumerate(self._critical_salience_items(context.salience_assessment)):
            if any(
                self._scene_covers_signal(
                    scene,
                    candidate_id=item.candidate_id,
                    signal_text=item.content,
                    evidence_quote=item.evidence_quote,
                )
                for scene in scenes
            ):
                continue

            target_scene = self._repair_target_scene(
                scenes,
                artifact_type=artifact_type,
                index_hint=index,
            )
            if item.candidate_id in context.claim_ids and item.candidate_id not in target_scene.claim_refs:
                target_scene.claim_refs.append(item.candidate_id)

            if artifact_type == "comparison_one_pager":
                target_scene.visual_hierarchy = self._append_unique(target_scene.visual_hierarchy, item.content)
                target_scene.modules.append(
                    SceneModuleSchema(
                        module_id=f"critical-{len(target_scene.modules) + 1}",
                        label=item.content[:80],
                        purpose="Cover a mandatory one-pager module.",
                        content_type="claim_cluster",
                        claim_refs=[item.candidate_id] if item.candidate_id in context.claim_ids else [],
                    )
                )
                target_scene.narration_focus = self._prepend_guidance(target_scene.narration_focus, item.content)
            elif artifact_type == "slide_thumbnail":
                target_scene.focal_subject = target_scene.focal_subject or item.content
                target_scene.visual_hierarchy = self._prepend_unique(target_scene.visual_hierarchy, item.content, limit=3)
                target_scene.narration_focus = self._prepend_guidance(target_scene.narration_focus, item.content)
                target_scene.claim_refs = target_scene.claim_refs[:2]
            elif artifact_type == "technical_infographic":
                target_scene.visual_hierarchy = self._append_unique(target_scene.visual_hierarchy, item.content)
                target_scene.modules.append(
                    SceneModuleSchema(
                        module_id=f"critical-{len(target_scene.modules) + 1}",
                        label=item.content[:80],
                        purpose="Represent a mandatory mechanism component.",
                        content_type="claim_cluster",
                        claim_refs=[item.candidate_id] if item.candidate_id in context.claim_ids else [],
                    )
                )
                target_scene.narration_focus = self._append_guidance(target_scene.narration_focus, item.content)
            elif artifact_type == "process_diagram":
                target_scene.flow_steps = self._append_unique(target_scene.flow_steps, item.content)
                target_scene.modules.append(
                    SceneModuleSchema(
                        module_id=f"critical-{len(target_scene.modules) + 1}",
                        label=item.content[:80],
                        purpose="Represent a mandatory process step.",
                        content_type="process_step",
                        claim_refs=[item.candidate_id] if item.candidate_id in context.claim_ids else [],
                    )
                )
                target_scene.narration_focus = self._append_guidance(target_scene.narration_focus, item.content)
            else:
                target_scene.narration_focus = self._append_guidance(target_scene.narration_focus, item.content)

        forward_pull = context.forward_pull
        if forward_pull is None:
            return repaired

        first_scene = scenes[0]
        if context.artifact_policy.planning_mode == "sequential":
            first_scene.scene_role = "bait_hook"
            if forward_pull.bait and forward_pull.bait.content:
                first_scene.title = first_scene.title if self._text_matches_signal(first_scene.title, forward_pull.bait.content) else (forward_pull.bait.content[:96] if "scene" in first_scene.title.lower() or "opening" in first_scene.title.lower() else first_scene.title)
                first_scene.narration_focus = self._prepend_guidance(first_scene.narration_focus, forward_pull.bait.content)
            if forward_pull.hook and forward_pull.hook.question:
                first_scene.narration_focus = self._prepend_guidance(
                    first_scene.narration_focus,
                    f"Driving question: {forward_pull.hook.question}",
                )

            last_scene = scenes[-1]
            last_scene.scene_role = "payoff"
            if forward_pull.rewards:
                last_scene.narration_focus = self._append_guidance(
                    last_scene.narration_focus,
                    forward_pull.rewards[0].payoff_signal,
                )
            if forward_pull.payloads:
                last_scene.narration_focus = self._append_guidance(
                    last_scene.narration_focus,
                    f"End on {forward_pull.payloads[0].theme_or_engine}",
                )
        elif artifact_type == "comparison_one_pager":
            if forward_pull.hook and forward_pull.hook.question:
                first_scene.title = forward_pull.hook.question[:100]
                first_scene.narration_focus = self._prepend_guidance(first_scene.narration_focus, forward_pull.hook.question)
            if forward_pull.payloads:
                payload_text = forward_pull.payloads[0].theme_or_engine
                first_scene.scene_goal = self._append_guidance(
                    first_scene.scene_goal,
                    f"Land the synthesis on {payload_text}",
                )
                first_scene.visual_hierarchy = self._append_unique(
                    first_scene.visual_hierarchy,
                    "synthesis panel",
                )
            if not first_scene.modules:
                first_scene.modules.extend(
                    [
                        SceneModuleSchema(
                            module_id="hook-header",
                            label="Hook Header",
                            purpose="Open with the core framing question or promise.",
                            content_type="hero",
                            claim_refs=first_scene.claim_refs[:1],
                            placement_hint="top band",
                        ),
                        SceneModuleSchema(
                            module_id="core-module-1",
                            label="Core Module",
                            purpose="Explain the most important source-grounded idea.",
                            content_type="claim_cluster",
                            claim_refs=first_scene.claim_refs[:2],
                            placement_hint="main body",
                        ),
                        SceneModuleSchema(
                            module_id="synthesis-panel",
                            label="Synthesis",
                            purpose="Land the final takeaway or durable meaning of the board.",
                            content_type="support_panel",
                            claim_refs=first_scene.claim_refs[-2:],
                            placement_hint="bottom band",
                        ),
                    ]
                )
        elif artifact_type == "slide_thumbnail":
            anchor_signal = ""
            if forward_pull.hook and forward_pull.hook.question and len(forward_pull.hook.question.split()) <= 10:
                anchor_signal = forward_pull.hook.question
            elif forward_pull.bait and forward_pull.bait.content:
                anchor_signal = forward_pull.bait.content
            if anchor_signal:
                first_scene.title = self._short_headline(anchor_signal, max_words=8, max_chars=56) or first_scene.title
                first_scene.focal_subject = anchor_signal
                first_scene.visual_hierarchy = self._prepend_unique(first_scene.visual_hierarchy, anchor_signal, limit=3)
            if forward_pull.hook and forward_pull.hook.question:
                first_scene.narration_focus = self._prepend_guidance(first_scene.narration_focus, forward_pull.hook.question)
            first_scene.claim_refs = first_scene.claim_refs[:2]

        return repaired

    @staticmethod
    def _outline_snapshot_from_script_pack(script_pack: ScriptPack) -> list[dict[str, Any]]:
        return [
            {
                "scene_id": scene.scene_id,
                "title": scene.title,
                "narration_focus": scene.narration_focus,
                "visual_prompt": scene.visual_prompt,
                "claim_refs": scene.claim_refs,
                "scene_mode": scene.scene_mode,
                "scene_role": scene.scene_role,
                "composition_goal": scene.composition_goal,
                "layout_template": scene.layout_template,
                "focal_subject": scene.focal_subject,
                "visual_hierarchy": scene.visual_hierarchy,
                "comparison_axes": scene.comparison_axes,
                "flow_steps": scene.flow_steps,
                "crop_safe_regions": scene.crop_safe_regions,
                "evidence_refs": scene.evidence_refs,
                "source_media": [item.model_dump() for item in scene.source_media],
                "render_strategy": scene.render_strategy,
            }
            for scene in script_pack.scenes
        ]

    @staticmethod
    def _build_replan_directives(
        *,
        report: PlannerValidationReport,
        script_pack: ScriptPack,
    ) -> str:
        hard_lines = "\n".join(f"- {issue.message}" for issue in report.hard_issues[:8])
        draft_snapshot = json.dumps(
            GeminiStoryAgent._outline_snapshot_from_script_pack(script_pack),
            ensure_ascii=True,
        )
        return (
            "REVISION REQUIRED:\n"
            "The previous outline failed these mandatory checks:\n"
            f"{hard_lines}\n"
            "Keep the same artifact type and scene count. Return a full corrected outline only.\n"
            f"PREVIOUS DRAFT:\n{draft_snapshot}"
        )

    @staticmethod
    def _build_planner_qa_summary(
        *,
        initial_report: PlannerValidationReport,
        final_report: PlannerValidationReport,
        repair_applied: bool,
        replan_attempted: bool,
    ) -> PlannerQaSummary:
        if replan_attempted:
            mode: Literal["direct", "repaired", "replanned"] = "replanned"
            summary = "Planner used one constrained replan after mandatory checks still failed."
        elif repair_applied:
            mode = "repaired"
            summary = "Planner applied deterministic repairs before locking the script pack."
        else:
            mode = "direct"
            summary = "Planner locked the script pack directly with no mandatory fixes."

        details: list[str] = []
        if initial_report.hard_issues:
            details.append(f"Initial mandatory issues: {len(initial_report.hard_issues)}.")
        if initial_report.warnings:
            details.append(f"Initial warnings: {len(initial_report.warnings)}.")
        if repair_applied:
            details.append("Coverage and structural hooks were repaired before final lock.")
        if replan_attempted:
            details.append("One constrained replan was requested with explicit failure notes.")
        if final_report.warnings:
            details.append(f"Final warnings remaining: {len(final_report.warnings)}.")
            details.extend(issue.message for issue in final_report.warnings[:2])

        return PlannerQaSummary(
            mode=mode,
            summary=summary,
            initial_hard_issue_count=len(initial_report.hard_issues),
            initial_warning_count=len(initial_report.warnings),
            final_warning_count=len(final_report.warnings),
            repair_applied=repair_applied,
            replan_attempted=replan_attempted,
            details=details[:4],
        )

    async def _run_salience_pass(
        self,
        *,
        source_text: str,
        content_signal: dict[str, Any],
        artifact_policy: ArtifactPlanningPolicy,
    ) -> SalienceAssessmentSchema | None:
        if artifact_policy.salience_pass == "OFF":
            return None

        candidates = self._salience_candidates(
            content_signal=content_signal,
            mode=artifact_policy.salience_pass,
            planning_mode=artifact_policy.planning_mode,
        )
        if not candidates:
            return None

        try:
            response = await self.client.aio.models.generate_content(
                model=self._planner_precompute_model(),
                contents=self._build_salience_prompt(source_text=source_text, candidates=candidates),
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=SalienceAssessmentSchema,
                ),
            )
            return SalienceAssessmentSchema.model_validate_json(response.text)
        except Exception as exc:
            print(f"Salience pass failed: {exc}")
            return None

    async def _run_forward_pull_pass(
        self,
        *,
        source_text: str,
        artifact_policy: ArtifactPlanningPolicy,
    ) -> ForwardPullSchema | None:
        if artifact_policy.forward_pull_pass == "OFF" or not source_text.strip():
            return None

        try:
            response = await self.client.aio.models.generate_content(
                model=self._planner_precompute_model(),
                contents=self._build_forward_pull_prompt(source_text=source_text),
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=ForwardPullSchema,
                ),
            )
            return ForwardPullSchema.model_validate_json(response.text)
        except Exception as exc:
            print(f"Forward-pull pass failed: {exc}")
            return None

    @staticmethod
    def _should_split_static_artifact(
        *,
        content_signal: dict[str, Any],
        artifact_type: str,
    ) -> bool:
        if artifact_type not in {"technical_infographic", "process_diagram"}:
            return False

        beats = content_signal.get("narrative_beats", [])
        claims = content_signal.get("key_claims", [])
        if not isinstance(beats, list) or not isinstance(claims, list):
            return False

        if artifact_type == "technical_infographic":
            return len(claims) >= 6 and len(beats) >= 4
        return len(beats) >= 5 and len(claims) >= 4

    @staticmethod
    def _derive_scene_count(
        *,
        artifact_policy: ArtifactPlanningPolicy,
        content_signal: dict[str, Any],
        render_profile: dict[str, Any],
        audience_level: str,
    ) -> tuple[int, str]:
        artifact_type = artifact_policy.artifact_type
        scene_budget = artifact_policy.scene_budget
        if artifact_policy.planning_mode != "sequential":
            if artifact_type == "comparison_one_pager":
                return 1, "Comparison one-pagers always plan as one dense composed scene."
            if artifact_type == "slide_thumbnail":
                return 1, "Slide thumbnails default to one hero frame; variants are optional and off by default."
            if GeminiStoryAgent._should_split_static_artifact(
                content_signal=content_signal,
                artifact_type=artifact_type,
            ):
                return 2, "Source naturally splits into overview and detail, so the static artifact uses two panels."
            return scene_budget.default, "Static artifacts stay dense rather than expanding with duration."

        output_controls = render_profile.get("output_controls", {})
        target_duration = output_controls.get("target_duration_sec", 60)
        density = str(render_profile.get("density", "standard")).lower()
        sec_per_scene = 10 if density == "detailed" else (18 if density == "simple" else 14)

        base_scenes = math.ceil(target_duration / sec_per_scene)
        claims = content_signal.get("key_claims", [])
        claims_count = len(claims) if isinstance(claims, list) else 0
        if claims_count > 5:
            base_scenes += 1
        if audience_level == "beginner":
            base_scenes -= 1

        scene_count = max(scene_budget.minimum, min(base_scenes, scene_budget.maximum))
        reason = (
            f"Sequential scene budget derived from target_duration_sec={target_duration}, "
            f"density={density}, claims={claims_count}, audience_level={audience_level}."
        )
        return scene_count, reason

    @staticmethod
    def _default_scene_role(idx: int, total: int) -> str:
        if total <= 1:
            return "payload"
        if idx == 1:
            return "bait_hook"
        if idx == total:
            return "payoff"
        if idx == 2:
            return "setup"
        if idx == total - 1:
            return "stakes"
        return "turn"

    @staticmethod
    def _default_layout_template(
        *,
        artifact_type: str,
        scene_index: int,
        scene_count: int,
    ) -> str | None:
        if artifact_type == "comparison_one_pager":
            return "modular_poster"
        if artifact_type == "slide_thumbnail":
            return "hero_thumbnail" if scene_index == 1 else "thumbnail_variant"
        if artifact_type == "technical_infographic":
            return "layered_mechanism" if scene_count == 1 or scene_index == 1 else "detail_callout"
        if artifact_type == "process_diagram":
            return "process_flow" if scene_count == 1 or scene_index == 1 else "zoom_detail"
        return None

    @staticmethod
    def _fallback_scene_plan(
        *,
        idx: int,
        scene_count: int,
        thesis: str,
        artifact_policy: ArtifactPlanningPolicy,
        claim_ids: list[str],
    ) -> ScenePlanSchema:
        shared_claim_refs = claim_ids[: min(4, len(claim_ids))]
        if artifact_policy.artifact_type == "comparison_one_pager":
            return ScenePlanSchema(
                scene_id=f"scene-{idx}",
                title="One-Pager Board",
                narration_focus=f"Guide the viewer through the core modules and takeaway inside {thesis}.",
                visual_prompt=(
                    "A single dense editorial-style one-pager board with modular sections, "
                    "clear hierarchy, strong containers, diagrams, callouts, and no reliance on tiny image text."
                ),
                claim_refs=shared_claim_refs,
                scene_mode="static",
                composition_goal="Compose one publish-ready poster-style information board.",
                layout_template="modular_poster",
                visual_hierarchy=["hook header", "core modules", "evidence/data callouts", "synthesis panel"],
                modules=[
                    SceneModuleSchema(
                        module_id="hook-header",
                        label="Hook Header",
                        purpose="Open with the core framing question or promise.",
                        content_type="hero",
                        claim_refs=shared_claim_refs[:1],
                        placement_hint="top band",
                    ),
                    SceneModuleSchema(
                        module_id="core-module-1",
                        label="Core Module",
                        purpose="Explain the most important source-grounded idea.",
                        content_type="claim_cluster",
                        claim_refs=shared_claim_refs[:2],
                        placement_hint="upper-left body",
                    ),
                    SceneModuleSchema(
                        module_id="evidence-callout",
                        label="Evidence Callout",
                        purpose="Anchor the board in source-grounded evidence or key support points.",
                        content_type="callout",
                        claim_refs=shared_claim_refs[1:3],
                        placement_hint="side rail",
                    ),
                    SceneModuleSchema(
                        module_id="synthesis-panel",
                        label="Synthesis",
                        purpose="Land the final takeaway or durable meaning of the board.",
                        content_type="support_panel",
                        claim_refs=shared_claim_refs[-2:],
                        placement_hint="bottom band",
                    ),
                ],
            )
        if artifact_policy.artifact_type == "slide_thumbnail":
            return ScenePlanSchema(
                scene_id=f"scene-{idx}",
                title="Hero Thumbnail",
                narration_focus=f"Land the hook for {thesis} in one instantly readable hero frame.",
                visual_prompt=(
                    "A bold thumbnail-style hero frame with one dominant subject, strong silhouette, "
                    "high contrast, a reserved headline-safe area, one supporting context cue, and no generic abstract symbols."
                ),
                claim_refs=claim_ids[:1],
                scene_mode="static",
                composition_goal="Create a single hero frame that reads instantly at small size and supports future headline overlay.",
                layout_template="hero_thumbnail" if idx == 1 else "thumbnail_variant",
                focal_subject=thesis,
                visual_hierarchy=["headline-safe hook zone", "hero subject", "supporting context cue"],
                crop_safe_regions=["top-left headline zone", "center hero safe area"],
            )
        if artifact_policy.artifact_type == "technical_infographic":
            title = "System Overview" if idx == 1 else "Mechanism Detail"
            return ScenePlanSchema(
                scene_id=f"scene-{idx}",
                title=title,
                narration_focus=f"Explain the core mechanism behind {thesis} with structured clarity.",
                visual_prompt="A clean technical infographic with layered modules, annotations implied visually, and no image text.",
                claim_refs=shared_claim_refs,
                scene_mode="static",
                composition_goal="Organize the mechanism into a structured explanatory board.",
                layout_template="layered_mechanism" if idx == 1 else "detail_callout",
                visual_hierarchy=["system overview", "core mechanism", "supporting detail"],
            )
        if artifact_policy.artifact_type == "process_diagram":
            title = "Process Flow" if idx == 1 else "Flow Detail"
            return ScenePlanSchema(
                scene_id=f"scene-{idx}",
                title=title,
                narration_focus=f"Walk through the process logic of {thesis} in the correct order.",
                visual_prompt="A clear process diagram showing stages, transitions, and decision points without text labels inside the image.",
                claim_refs=shared_claim_refs,
                scene_mode="static",
                composition_goal="Map the process as a single readable flow.",
                layout_template="process_flow" if idx == 1 else "zoom_detail",
                flow_steps=["entry", "transition", "outcome"] if idx == 1 else ["detail focus", "state change"],
                visual_hierarchy=["entry state", "core steps", "outcome"],
            )

        return ScenePlanSchema(
            scene_id=f"scene-{idx}",
            title=f"Explainer Point {idx}",
            narration_focus=f"Further detail on {thesis}.",
            visual_prompt="A relevant educational visual.",
            claim_refs=claim_ids[max(0, idx - 1): max(0, idx - 1) + 2],
            scene_mode="sequential",
            scene_role=GeminiStoryAgent._default_scene_role(idx, scene_count),
        )

    @staticmethod
    def _normalize_scene_plans(
        *,
        parsed_scenes: list[ScenePlanSchema],
        target_scene_count: int,
        thesis: str,
        artifact_policy: ArtifactPlanningPolicy,
        claim_ids: list[str],
    ) -> list[ScenePlanSchema]:
        scenes = list(parsed_scenes[:target_scene_count])
        while len(scenes) < target_scene_count:
            idx = len(scenes) + 1
            scenes.append(
                GeminiStoryAgent._fallback_scene_plan(
                    idx=idx,
                    scene_count=target_scene_count,
                    thesis=thesis,
                    artifact_policy=artifact_policy,
                    claim_ids=claim_ids,
                )
            )

        normalized: list[ScenePlanSchema] = []
        for idx, scene in enumerate(scenes, start=1):
            scene_mode = "static" if artifact_policy.planning_mode != "sequential" else "sequential"
            normalized.append(
                scene.model_copy(
                    update={
                        "scene_mode": scene_mode,
                        "scene_role": scene.scene_role
                        or (
                            GeminiStoryAgent._default_scene_role(idx, len(scenes))
                            if artifact_policy.planning_mode == "sequential"
                            else None
                        ),
                        "layout_template": scene.layout_template
                        or GeminiStoryAgent._default_layout_template(
                            artifact_type=artifact_policy.artifact_type,
                            scene_index=idx,
                            scene_count=len(scenes),
                        ),
                    }
                )
            )
        return normalized

    @staticmethod
    def _build_script_pack_prompt(
        *,
        thesis: str,
        concepts: list[Any],
        beats: list[Any],
        key_claims: list[Any],
        visual_candidates: list[Any],
        audience_descriptor: str,
        taste_bar: str,
        must_include: list[str],
        must_avoid: list[str],
        artifact_policy: ArtifactPlanningPolicy,
        scene_count: int,
        salience_summary: str = "",
        forward_pull_guidance: str = "",
        repair_directives: str = "",
    ) -> str:
        prompt = (
            "SYSTEM:\n"
            "You are planning an ExplainFlow script pack.\n"
            "Return only valid JSON matching the provided schema.\n"
            "Do not add markdown or commentary.\n\n"
            "USER:\n"
            f"Artifact type: {artifact_policy.artifact_type}\n"
            f"Planning mode: {artifact_policy.planning_mode}\n"
            f"Script shape: {artifact_policy.script_shape}\n"
            f"Audience persona: {audience_descriptor}\n"
            f"Taste bar: {taste_bar}\n"
            f"Target scene count: {scene_count}\n"
            f"Core thesis: {thesis}\n"
            f"Concepts: {json.dumps(concepts[:10], ensure_ascii=True)}\n"
            f"Narrative beats: {json.dumps(beats[:10], ensure_ascii=True)}\n"
            f"Key claims: {json.dumps(key_claims[:8], ensure_ascii=True)}\n"
            f"Visual candidates: {json.dumps(visual_candidates[:8], ensure_ascii=True)}\n"
            f"Planner focus: {', '.join(artifact_policy.planner_focus)}.\n"
            f"Generation notes: {' '.join(artifact_policy.generator_notes)}\n"
        )
        if salience_summary:
            prompt += f"{salience_summary}\n"
        if forward_pull_guidance:
            prompt += f"{forward_pull_guidance}\n"

        if artifact_policy.planning_mode == "sequential":
            prompt += (
                "Create a scene-by-scene storyboard outline with progression across the full pack.\n"
                "Use scene_mode='sequential'. Provide scene_role values such as bait_hook, setup, turn, stakes, payoff.\n"
                "Ensure each scene has a descriptive title, a clear narration_focus, and a detailed visual_prompt.\n"
                "Map CRITICAL salience items across the pack before anything else.\n"
            )
        elif artifact_policy.artifact_type == "comparison_one_pager":
            prompt += (
                "Create exactly one static scene for a dense one-pager board.\n"
                "Do not create a narrative sequence or multiple scenes.\n"
                "Use scene_mode='static' and include composition_goal, layout_template, visual_hierarchy, and modules.\n"
                "Convert narrative beats into modules inside one board rather than separate scenes.\n"
                "Turn CRITICAL salience items into mandatory module content, evidence callouts, or synthesis content.\n"
                "Use hook and payload to shape the title, opening impression, and synthesis panel.\n"
                "Use visual_candidates only when their claim_refs align with the selected modules.\n"
                "Choose a layout_template such as modular_poster, editorial_grid, layered_explainer, or radial_overview.\n"
                "Create a board with 4 to 7 modules such as hook_header, core_module, evidence_callout, process_strip, definition_box, data_panel, or synthesis_panel.\n"
                "Keep narration_focus centered on how to read the board and what takeaway it lands, not on voiceover progression.\n"
                "Ensure visual_prompt describes one composed poster canvas with clear module zones, visual hierarchy, and a strong synthesis area.\n"
                "Prefer dense structure and readability over dramatic progression.\n"
                "Do not rely on dense tiny text inside the image; use clear zones, containers, icons, charts, diagrams, and strong layout instead.\n"
            )
        elif artifact_policy.artifact_type == "slide_thumbnail":
            prompt += (
                "Create a single static thumbnail concept, not a storyboard sequence.\n"
                "Do not create multiple scenes unless a variant is explicitly required.\n"
                "Use scene_mode='static' and include composition_goal, layout_template, focal_subject, crop_safe_regions, and visual_hierarchy.\n"
                "Choose one dominant hook and one dominant focal subject rather than spreading across multiple beats or claims.\n"
                "Use the strongest bait or hook as the thumbnail anchor.\n"
                "Use threat only if it sharpens curiosity without fabricating drama.\n"
                "Use reward only if it implies a clear payoff at a glance.\n"
                "Design for instant readability at small size.\n"
                "Reserve a clean headline-safe area and ensure strong crop safety.\n"
                "Favor silhouette clarity, contrast, one hero subject, and one supporting context cue.\n"
                "Avoid dense informational layouts, multi-panel structures, or poster-like composition.\n"
                "Keep the title short, punchy, and headline-like rather than explanatory.\n"
                "Ensure visual_prompt describes one bold hero frame with a clear focal hierarchy and click-through energy.\n"
            )
        elif artifact_policy.artifact_type == "technical_infographic":
            prompt += (
                "Create a static technical infographic plan. Use one scene unless overview plus detail is clearly necessary.\n"
                "Use scene_mode='static' and include composition_goal, layout_template, and visual_hierarchy.\n"
                "Threat and reward framing should be ignored unless they are directly explanatory and source-grounded.\n"
            )
        elif artifact_policy.artifact_type == "process_diagram":
            prompt += (
                "Create a static process-map plan. Use one scene unless overview plus detail is clearly necessary.\n"
                "Use scene_mode='static' and include composition_goal, layout_template, flow_steps, and visual_hierarchy.\n"
                "Prioritize ordered process logic over suspense framing.\n"
            )

        if must_include:
            prompt += f"Must include: {', '.join(must_include)}.\n"
        if must_avoid:
            prompt += f"Must avoid: {', '.join(must_avoid)}.\n"
        if repair_directives:
            prompt += f"{repair_directives}\n"
        return prompt

    @staticmethod
    def _compile_script_pack(
        *,
        plan_id: str,
        thesis: str,
        audience_descriptor: str,
        scenes: list[ScenePlanSchema],
        must_include: list[str],
        must_avoid: list[str],
        artifact_policy: ArtifactPlanningPolicy,
        scene_budget_reason: str,
    ) -> ScriptPack:
        script_scenes: list[ScriptPackScene] = []

        for idx, scene in enumerate(scenes, start=1):
            scene_id = normalized_scene_id(scene.scene_id, idx)
            title = (scene.title or f"Scene {idx}").strip()
            narration_focus = (
                scene.narration_focus
                or f"Explain core point {idx} about {thesis}."
            ).strip()
            visual_prompt = (
                scene.visual_prompt
                or "Generate a precise educational visual that supports the narration."
            ).strip()
            claim_refs = [ref for ref in scene.claim_refs if isinstance(ref, str) and ref.strip()]
            scene_mode = "static" if artifact_policy.planning_mode != "sequential" else "sequential"
            continuity_refs: list[str] = []
            if idx > 1:
                if scene_mode == "sequential":
                    continuity_refs.append(f"Maintain continuity from scene-{idx - 1}.")
                else:
                    continuity_refs.append(f"Preserve the same composition language from scene-{idx - 1}.")
            continuity_refs.extend(extract_anchor_terms(title, limit=2))

            acceptance_checks = [
                "Narration is between 50 and 100 words.",
                "Narration is plain spoken prose with no labels or markdown.",
                "Visual and narration align with the stated scene focus.",
            ]
            if scene_mode == "static":
                acceptance_checks.append("Treat this as a single composed canvas, not a cinematic beat sequence.")
            if artifact_policy.artifact_type == "comparison_one_pager":
                acceptance_checks[0] = "Narration is between 60 and 90 words."
                acceptance_checks.append("Keep the one-pager modular structure legible, dense, and publish-ready.")
            if artifact_policy.artifact_type == "slide_thumbnail":
                acceptance_checks[0] = "Narration is between 18 and 40 words."
                acceptance_checks.append("Ensure the image reads instantly and stays strong at small size.")
            if artifact_policy.artifact_type in {"technical_infographic", "process_diagram"}:
                acceptance_checks[0] = "Narration is between 40 and 85 words."
                acceptance_checks.append("Prioritize structural clarity over dramatic escalation.")
            if must_include:
                acceptance_checks.append(
                    f"Prefer these audience cues: {', '.join(must_include[:4])}."
                )
            if must_avoid:
                acceptance_checks.append(
                    f"Avoid these patterns: {', '.join(must_avoid[:4])}."
                )

            if scene_mode == "sequential":
                scene_goal = f"Deliver scene {idx} of the explainer clearly for {audience_descriptor}."
            else:
                scene_goal = (
                    f"Compose scene {idx} as a single {artifact_policy.script_shape.replace('_', ' ')} "
                    f"for {audience_descriptor}."
                )

            script_scenes.append(
                ScriptPackScene(
                    scene_id=scene_id,
                    title=title,
                    scene_goal=scene_goal,
                    narration_focus=narration_focus,
                    visual_prompt=visual_prompt,
                    claim_refs=claim_refs,
                    continuity_refs=continuity_refs,
                    acceptance_checks=acceptance_checks,
                    scene_mode=scene_mode,
                    scene_role=scene.scene_role,
                    composition_goal=scene.composition_goal,
                    layout_template=scene.layout_template
                    or GeminiStoryAgent._default_layout_template(
                        artifact_type=artifact_policy.artifact_type,
                        scene_index=idx,
                        scene_count=len(scenes),
                    ),
                    focal_subject=scene.focal_subject,
                    visual_hierarchy=scene.visual_hierarchy,
                    modules=scene.modules,
                    comparison_axes=scene.comparison_axes,
                    flow_steps=scene.flow_steps,
                    crop_safe_regions=scene.crop_safe_regions,
                    evidence_refs=scene.evidence_refs,
                    source_media=scene.source_media,
                    render_strategy=scene.render_strategy,
                )
            )

        if artifact_policy.planning_mode == "sequential":
            plan_summary = f"{thesis} explained through {len(script_scenes)} cohesive scenes."
        elif artifact_policy.artifact_type == "comparison_one_pager":
            plan_summary = f"{thesis} organized into a single one-pager board."
        elif artifact_policy.artifact_type == "slide_thumbnail":
            plan_summary = f"{thesis} condensed into {len(script_scenes)} thumbnail concept."
        elif artifact_policy.artifact_type == "technical_infographic":
            plan_summary = f"{thesis} structured as a technical infographic."
        else:
            plan_summary = f"{thesis} mapped as a static process-focused explainer."

        return ScriptPack(
            plan_id=plan_id,
            plan_summary=plan_summary,
            audience_descriptor=audience_descriptor,
            scene_count=len(script_scenes),
            artifact_type=artifact_policy.artifact_type,
            planning_mode=artifact_policy.planning_mode,
            script_shape=artifact_policy.script_shape,
            scene_budget_reason=scene_budget_reason,
            salience_mode=artifact_policy.salience_pass,
            forward_pull_mode=artifact_policy.forward_pull_pass,
            scenes=script_scenes,
        )

    def _outline_to_script_pack(
        self,
        *,
        outline_text: str,
        scene_count: int,
        thesis: str,
        audience_descriptor: str,
        artifact_policy: ArtifactPlanningPolicy,
        claim_ids: list[str],
        must_include: list[str],
        must_avoid: list[str],
        scene_budget_reason: str,
    ) -> ScriptPack:
        parsed_outline = OutlineSchema.model_validate_json(outline_text)
        scenes = self._normalize_scene_plans(
            parsed_scenes=parsed_outline.scenes,
            target_scene_count=scene_count,
            thesis=thesis,
            artifact_policy=artifact_policy,
            claim_ids=claim_ids,
        )
        return self._compile_script_pack(
            plan_id=f"script-pack-{int(time.time())}",
            thesis=thesis,
            audience_descriptor=audience_descriptor,
            scenes=scenes,
            must_include=must_include,
            must_avoid=must_avoid,
            artifact_policy=artifact_policy,
            scene_budget_reason=scene_budget_reason,
        )

    async def _plan_script_pack(
        self,
        *,
        source_text: str,
        normalized_source_text: str,
        content_signal: dict[str, Any],
        render_profile: dict[str, Any],
        artifact_scope: list[ArtifactName],
    ) -> tuple[ScriptPack, dict[str, Any], PlannerQaSummary]:
        audience_cfg = render_profile.get("audience", {})
        audience_level = str(audience_cfg.get("level", "beginner")).lower()
        audience_persona = str(audience_cfg.get("persona", "General audience")).strip()
        domain_context = str(audience_cfg.get("domain_context", "")).strip()
        taste_bar = str(audience_cfg.get("taste_bar", "standard")).lower()
        must_include = [
            str(item).strip()
            for item in audience_cfg.get("must_include", [])
            if isinstance(item, str) and str(item).strip()
        ][:8]
        must_avoid = [
            str(item).strip()
            for item in audience_cfg.get("must_avoid", [])
            if isinstance(item, str) and str(item).strip()
        ][:8]

        thesis = content_signal.get("thesis", {}).get("one_liner", "A generic topic")
        concepts = content_signal.get("concepts", [])
        beats = content_signal.get("narrative_beats", [])
        key_claims = content_signal.get("key_claims", [])
        visual_candidates = content_signal.get("visual_candidates", [])
        claim_ids = [
            str(claim.get("claim_id")).strip()
            for claim in key_claims
            if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
        ]
        audience_descriptor = f"{audience_persona} ({audience_level})"
        if domain_context:
            audience_descriptor += f" in {domain_context}"

        artifact_policy = self._resolve_artifact_policy(
            render_profile=render_profile,
            artifact_scope=artifact_scope,
        )
        planner_source_text = self._planner_source_text(
            source_text=source_text,
            normalized_source_text=normalized_source_text,
            content_signal=content_signal,
        )
        salience_assessment, forward_pull = await asyncio.gather(
            self._run_salience_pass(
                source_text=planner_source_text,
                content_signal=content_signal,
                artifact_policy=artifact_policy,
            ),
            self._run_forward_pull_pass(
                source_text=planner_source_text,
                artifact_policy=artifact_policy,
            ),
        )
        scene_count, scene_budget_reason = self._derive_scene_count(
            artifact_policy=artifact_policy,
            content_signal=content_signal,
            render_profile=render_profile,
            audience_level=audience_level,
        )
        context = self._build_enrichment_context(
            artifact_policy=artifact_policy,
            thesis=thesis,
            audience_descriptor=audience_descriptor,
            claim_ids=claim_ids,
            scene_count=scene_count,
            salience_assessment=salience_assessment,
            forward_pull=forward_pull,
        )
        planning_prompt = self._build_script_pack_prompt(
            thesis=thesis,
            concepts=concepts if isinstance(concepts, list) else [],
            beats=beats if isinstance(beats, list) else [],
            key_claims=key_claims if isinstance(key_claims, list) else [],
            visual_candidates=visual_candidates if isinstance(visual_candidates, list) else [],
            audience_descriptor=audience_descriptor,
            taste_bar=taste_bar,
            must_include=must_include,
            must_avoid=must_avoid,
            artifact_policy=artifact_policy,
            scene_count=scene_count,
            salience_summary=self._best_effort_salience_summary(salience_assessment),
            forward_pull_guidance=self._forward_pull_guidance(
                artifact_policy=artifact_policy,
                forward_pull=forward_pull,
            ),
        )

        plan_response = await self.client.aio.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=planning_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
                response_schema=OutlineSchema,
            ),
        )
        draft_script_pack = self._outline_to_script_pack(
            outline_text=plan_response.text,
            scene_count=scene_count,
            thesis=thesis,
            audience_descriptor=audience_descriptor,
            artifact_policy=artifact_policy,
            claim_ids=claim_ids,
            must_include=must_include,
            must_avoid=must_avoid,
            scene_budget_reason=scene_budget_reason,
        )
        initial_report = self._validate_script_pack_against_enrichments(
            script_pack=draft_script_pack,
            context=context,
        )
        script_pack = self._repair_script_pack_from_enrichments(
            script_pack=draft_script_pack,
            context=context,
        )
        repair_applied = script_pack.model_dump() != draft_script_pack.model_dump()
        report = self._validate_script_pack_against_enrichments(
            script_pack=script_pack,
            context=context,
        )
        replan_attempted = False

        if report.has_hard_issues:
            replan_attempted = True
            replan_prompt = self._build_script_pack_prompt(
                thesis=thesis,
                concepts=concepts if isinstance(concepts, list) else [],
                beats=beats if isinstance(beats, list) else [],
                key_claims=key_claims if isinstance(key_claims, list) else [],
                visual_candidates=visual_candidates if isinstance(visual_candidates, list) else [],
                audience_descriptor=audience_descriptor,
                taste_bar=taste_bar,
                must_include=must_include,
                must_avoid=must_avoid,
                artifact_policy=artifact_policy,
                scene_count=scene_count,
                salience_summary=self._best_effort_salience_summary(salience_assessment),
                forward_pull_guidance=self._forward_pull_guidance(
                    artifact_policy=artifact_policy,
                    forward_pull=forward_pull,
                ),
                repair_directives=self._build_replan_directives(
                    report=report,
                    script_pack=script_pack,
                ),
            )
            replan_response = await self.client.aio.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=replan_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    response_mime_type="application/json",
                    response_schema=OutlineSchema,
                ),
            )
            replanned_draft = self._outline_to_script_pack(
                outline_text=replan_response.text,
                scene_count=scene_count,
                thesis=thesis,
                audience_descriptor=audience_descriptor,
                artifact_policy=artifact_policy,
                claim_ids=claim_ids,
                must_include=must_include,
                must_avoid=must_avoid,
                scene_budget_reason=scene_budget_reason,
            )
            script_pack = self._repair_script_pack_from_enrichments(
                script_pack=replanned_draft,
                context=context,
            )
            repair_applied = repair_applied or (script_pack.model_dump() != replanned_draft.model_dump())
            report = self._validate_script_pack_against_enrichments(
                script_pack=script_pack,
                context=context,
            )
            if report.has_hard_issues:
                issues = "; ".join(issue.message for issue in report.hard_issues[:6])
                raise ValueError(f"Script pack failed mandatory enrichment checks: {issues}")

        scene_claim_map = {
            scene.scene_id: [claim_ref for claim_ref in scene.claim_refs if claim_ref]
            for scene in script_pack.scenes
        }
        claim_traceability = self._claim_traceability_summary(
            claim_ids=claim_ids,
            scene_claim_map=scene_claim_map,
        )
        planner_qa_summary = self._build_planner_qa_summary(
            initial_report=initial_report,
            final_report=report,
            repair_applied=repair_applied,
            replan_attempted=replan_attempted,
        )
        return script_pack, claim_traceability, planner_qa_summary

    async def _stream_scene_assets(
        self,
        request: Request,
        scene_id: str,
        topic: str,
        audience: str,
        tone: str,
        scene_title: str,
        narration_focus: str,
        style_guide: str,
        visual_prompt: str,
        image_prefix: str,
        audio_prefix: str,
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
        result_collector: dict[str, Any] | None = None,
        trace_payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, str]]:
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

        if artifact_type == "comparison_one_pager":
            scene_prompt = (
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
                "2) The text must be 60-90 words.\n"
                "3) The text must explain how to read the board and the main takeaway.\n"
                "4) Immediately after the text, generate the corresponding high-quality inline image.\n"
                "5) The image MUST be a single composed one-pager canvas that matches the visual direction.\n"
                "6) DO NOT output any other text or conversational filler."
            )
        elif artifact_type == "slide_thumbnail":
            scene_prompt = (
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
                "2) The text must be 18-40 words.\n"
                "3) The text must explain the hook and why the visual frame is compelling.\n"
                "4) Immediately after the text, generate the corresponding high-quality inline image.\n"
                "5) The image MUST be a single composed thumbnail frame that matches the visual direction.\n"
                "6) DO NOT output any other text or conversational filler."
            )
        else:
            scene_prompt = (
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
                "2) The text must be 50-100 words.\n"
                "3) Immediately after the text, generate the corresponding high-quality inline image. "
                "The image MUST accurately depict the specific scientific or historical details mentioned in the text.\n"
                "4) DO NOT output any other text or conversational filler."
            )

        current_scene_text = ""
        latest_image_url = ""
        audio_url = ""
        max_attempts = 3

        for attempt in range(max_attempts):
            emitted_any_chunk = False
            try:
                response_stream = await self.client.aio.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=scene_prompt,
                    config=types.GenerateContentConfig(temperature=0.7),
                )

                async for chunk in response_stream:
                    if await request.is_disconnected():
                        return

                    text_parts, image_parts = extract_parts_from_chunk(chunk)
                    if not text_parts and not image_parts:
                        continue

                    emitted_any_chunk = True

                    for text in text_parts:
                        current_scene_text, delta = append_text_part(current_scene_text, text)
                        if not delta:
                            continue
                        payload: dict[str, Any] = {"scene_id": scene_id, "delta": delta}
                        if trace_payload:
                            payload["trace"] = trace_payload
                        yield build_sse_event(
                            "story_text_delta",
                            payload,
                        )

                    for image_bytes in image_parts:
                        latest_image_url = save_image_and_get_url(
                            request=request,
                            scene_id=scene_id,
                            image_bytes=image_bytes,
                            prefix=image_prefix,
                        )
                        payload = {"scene_id": scene_id, "url": latest_image_url}
                        if trace_payload:
                            payload["trace"] = trace_payload
                        yield build_sse_event(
                            "diagram_ready",
                            payload,
                        )
                break
            except Exception as exc:
                is_retryable = (
                    self._is_resource_exhausted(exc)
                    and not self._is_daily_quota_exhausted(exc)
                    and not emitted_any_chunk
                    and attempt < max_attempts - 1
                )
                if not is_retryable:
                    raise

                delay_sec = self._extract_retry_delay_seconds(exc) * (1.0 + 0.5 * attempt)
                yield build_sse_event(
                    "status",
                    {
                        "scene_id": scene_id,
                        "message": f"Rate limit reached. Retrying this scene in {int(round(delay_sec))}s...",
                        **({"trace": trace_payload} if trace_payload else {}),
                    },
                )
                await asyncio.sleep(delay_sec)

        if artifact_type == "slide_thumbnail" and latest_image_url and scene_title.strip():
            try:
                composited_image_url = compose_thumbnail_cover_and_get_url(
                    request=request,
                    scene_id=scene_id,
                    source_url=latest_image_url,
                    title=scene_title,
                    support_text=current_scene_text,
                    cue_lines=build_thumbnail_cover_cues(
                        title=scene_title,
                        claim_text_snippets=claim_text_snippets,
                        support_text=current_scene_text,
                        max_cues=2,
                    ),
                    prefix=f"{image_prefix}_cover",
                )
            except Exception as exc:
                print(f"Thumbnail cover composition failed for {scene_id}: {exc}")
            else:
                latest_image_url = composited_image_url
                payload = {"scene_id": scene_id, "url": latest_image_url}
                if trace_payload:
                    payload["trace"] = trace_payload
                yield build_sse_event("diagram_ready", payload)

        if current_scene_text.strip() and artifact_type != "slide_thumbnail":
            audio_url = generate_audio_and_get_url(
                request=request,
                scene_id=scene_id,
                text=current_scene_text,
                prefix=audio_prefix,
            )
            if audio_url:
                payload = {"scene_id": scene_id, "url": audio_url}
                if trace_payload:
                    payload["trace"] = trace_payload
                yield build_sse_event("audio_ready", payload)

        if result_collector is not None:
            result_collector["text"] = current_scene_text
            result_collector["image_url"] = latest_image_url
            result_collector["audio_url"] = audio_url
            result_collector["word_count"] = len(re.findall(r"\b[\w'-]+\b", current_scene_text))

    async def _execute_buffered_advanced_scene(
        self,
        *,
        request: Request,
        scene: ScriptPackScene,
        thesis: str,
        audience_descriptor: str,
        goal: str,
        style_guide: str,
        script_pack: ScriptPack,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        must_include: list[str],
        must_avoid: list[str],
        claim_text_snippets: list[str],
        evidence_text_snippets: list[str],
        active_continuity: list[str],
        scene_trace_payload: dict[str, Any],
        retry_reason_constraints: list[str] | None = None,
    ) -> BufferedSceneExecutionResult:
        events: list[dict[str, str]] = []
        scene_id = scene.scene_id
        scene_trace_id = str(scene_trace_payload.get("scene_trace_id", ""))

        events.append(
            build_sse_event(
                "scene_start",
                {
                    "scene_id": scene_id,
                    "title": scene.title,
                    "claim_refs": [claim_ref for claim_ref in scene.claim_refs if claim_ref],
                    "evidence_refs": [evidence_ref for evidence_ref in scene.evidence_refs if evidence_ref],
                    "render_strategy": scene.render_strategy,
                    "source_media": [item.model_dump() for item in scene.source_media],
                    "trace": scene_trace_payload,
                },
            )
        )

        for source_media_payload in self._resolve_source_media_payloads(
            request=request,
            scene_id=scene_id,
            source_media=scene.source_media,
            source_manifest=source_manifest,
        ):
            source_media_payload["trace"] = scene_trace_payload
            events.append(build_sse_event("source_media_ready", source_media_payload))

        retries_used = 0
        qa_result: dict[str, Any] = {
            "scene_id": scene_id,
            "status": "WARN",
            "score": 0.0,
            "reasons": ["Quality checks not executed."],
            "attempt": 1,
            "word_count": 0,
        }
        scene_result: dict[str, Any] = {}
        retry_constraints = list(retry_reason_constraints or [])

        for attempt_index in range(2):
            scene_result = {}
            attempt_constraints = list(scene.acceptance_checks)
            if retry_constraints:
                attempt_constraints.append(
                    f"Fix these QA issues from previous attempt: {'; '.join(retry_constraints[:3])}."
                )

            if attempt_index > 0:
                events.append(
                    build_sse_event(
                        "scene_retry_reset",
                        {
                            "scene_id": scene_id,
                            "retry_index": attempt_index,
                            "trace": scene_trace_payload,
                        },
                    )
                )

            async for event in self._stream_scene_assets(
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
                artifact_type=script_pack.artifact_type,
                scene_mode=scene.scene_mode,
                layout_template=scene.layout_template,
                focal_subject=scene.focal_subject,
                visual_hierarchy=scene.visual_hierarchy,
                modules=scene.modules,
                claim_refs=scene.claim_refs,
                claim_text_snippets=claim_text_snippets,
                evidence_text_snippets=evidence_text_snippets,
                crop_safe_regions=scene.crop_safe_regions,
                continuity_hints=active_continuity,
                extra_constraints=attempt_constraints,
                result_collector=scene_result,
                trace_payload=scene_trace_payload,
            ):
                events.append(event)

            qa_result = evaluate_scene_quality(
                scene=scene,
                generated_text=str(scene_result.get("text", "")),
                image_url=str(scene_result.get("image_url", "")),
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

        events.append(
            build_sse_event(
                "scene_done",
                {
                    "scene_id": scene_id,
                    "qa_status": qa_result["status"],
                    "auto_retries": retries_used,
                    "trace": scene_trace_payload,
                },
            )
        )

        return BufferedSceneExecutionResult(
            scene_id=scene_id,
            scene_trace_id=scene_trace_id,
            events=tuple(events),
            qa_result=qa_result,
            retries_used=retries_used,
            word_count=int(scene_result.get("word_count", 0)),
            continuity_tokens=tuple(extract_anchor_terms(str(scene_result.get("text", "")), limit=4)),
        )

    async def _extract_signal_one_pass(
        self,
        *,
        input_text: str,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        prompt_version: str,
        uploaded_assets: UploadedSourceAssets | None = None,
    ) -> dict[str, Any]:
        schema_str = self._load_schema_text("content_signal.schema.json")
        extraction_contents, _, _ = await self._build_signal_extraction_contents(
            document_text=input_text,
            source_manifest=source_manifest,
            schema_text=schema_str,
            version=prompt_version,
            uploaded_assets=uploaded_assets,
        )
        response = await self.client.aio.models.generate_content(
            model=self._signal_structural_model(),
            contents=extraction_contents,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        return self._parse_json_object_response(response.text)

    async def extract_signal(self, payload: SignalExtractionRequest) -> dict[str, Any]:
        run_id = self._new_run_id("extract-run")
        trace = init_trace_envelope(
            trace_id=f"trace-{uuid4().hex[:12]}",
            run_id=run_id,
            flow="extract_signal",
            artifact_scope=[],
        )
        uploaded_file_names: list[str] = []
        try:
            source_manifest = payload.source_manifest
            has_input_text = isinstance(payload.input_text, str) and bool(payload.input_text.strip())
            manifest = self._source_manifest_for_extraction(source_manifest)
            source_asset_count = len(manifest.assets) if manifest is not None else 0
            phase_timings_ms: dict[str, int] = {}
            if not has_input_text and source_asset_count == 0:
                raise ValueError("Provide source text or upload at least one source asset before extraction.")

            video_constraint_error = validate_video_manifest_constraints(
                source_manifest=source_manifest,
                source_text=payload.input_text,
                normalized_source_text=payload.normalized_source_text,
            )
            if video_constraint_error:
                raise ValueError(video_constraint_error)

            configured_version = os.getenv(
                "EXPLAINFLOW_SIGNAL_PROMPT_VERSION",
                SIGNAL_EXTRACTION_PROMPT_VERSION_DEFAULT,
            )
            prompt_version = configured_version.strip().lower()
            if prompt_version not in {"v1", "v2"}:
                prompt_version = SIGNAL_EXTRACTION_PROMPT_VERSION_DEFAULT
            extraction_mode = "single_pass"
            uploaded_asset_count = 0
            uploaded_assets = UploadedSourceAssets(parts=(), file_names=(), count=0)
            if source_asset_count:
                upload_started_at = time.perf_counter()
                uploaded_assets = await self._upload_source_asset_parts(
                    source_manifest=source_manifest,
                )
                phase_timings_ms["source_upload"] = int((time.perf_counter() - upload_started_at) * 1000)
                uploaded_file_names.extend(uploaded_assets.file_names)
                uploaded_asset_count = uploaded_assets.count

            if prompt_version == "v1":
                normalized_input_text = str(payload.input_text or "").strip()
                source_text_origin = "pasted_text" if normalized_input_text else None
                if (
                    normalized_input_text
                    and self._transcript_only_video_mode(source_manifest)
                    and self._transcript_needs_normalization(normalized_input_text)
                ):
                    normalization_started_at = time.perf_counter()
                    normalized_input_text, source_text_origin = await self._normalize_transcript_source_text(
                        source_text=normalized_input_text,
                        source_manifest=source_manifest,
                    )
                    phase_timings_ms["transcript_normalization"] = int((time.perf_counter() - normalization_started_at) * 1000)
                one_pass_started_at = time.perf_counter()
                signal_data = await self._extract_signal_one_pass(
                    input_text=normalized_input_text,
                    source_manifest=source_manifest,
                    prompt_version=prompt_version,
                    uploaded_assets=uploaded_assets,
                )
                phase_timings_ms["single_pass"] = int((time.perf_counter() - one_pass_started_at) * 1000)
                normalized_source_text = normalized_input_text
            else:
                recovery_started_at = time.perf_counter()
                normalized_source_text, source_text_origin = await self._recover_normalized_source_text(
                    input_text=payload.input_text,
                    normalized_source_text=payload.normalized_source_text,
                    source_text_origin=payload.source_text_origin,
                    source_manifest=source_manifest,
                    uploaded_assets=uploaded_assets,
                )
                phase_timings_ms["source_recovery"] = int((time.perf_counter() - recovery_started_at) * 1000)

                if (
                    normalized_source_text.strip()
                    and self._transcript_only_video_mode(source_manifest)
                    and self._transcript_needs_normalization(normalized_source_text)
                ):
                    normalization_started_at = time.perf_counter()
                    normalized_source_text, source_text_origin = await self._normalize_transcript_source_text(
                        source_text=normalized_source_text,
                        source_manifest=source_manifest,
                    )
                    phase_timings_ms["transcript_normalization"] = int((time.perf_counter() - normalization_started_at) * 1000)

                try:
                    if not normalized_source_text.strip():
                        raise ValueError("Unable to recover normalized source text from the uploaded source.")

                    structural_started_at = time.perf_counter()
                    structural_signal = await self._extract_signal_structural(
                        normalized_source_text=normalized_source_text,
                        source_manifest=source_manifest,
                        uploaded_assets=uploaded_assets,
                    )
                    phase_timings_ms["structural_extraction"] = int((time.perf_counter() - structural_started_at) * 1000)

                    creative_started_at = time.perf_counter()
                    creative_signal = await self._extract_signal_creative(
                        normalized_source_text=normalized_source_text,
                        structural_signal=structural_signal,
                        source_manifest=source_manifest,
                    )
                    phase_timings_ms["creative_extraction"] = int((time.perf_counter() - creative_started_at) * 1000)
                    signal_data = self._merge_signal_extraction_passes(
                        structural_signal=structural_signal,
                        creative_signal=creative_signal,
                    )
                    extraction_mode = "two_pass"
                except Exception as exc:
                    print(f"Two-pass extraction fallback: {exc}")
                    fallback_started_at = time.perf_counter()
                    signal_data = await self._extract_signal_one_pass(
                        input_text=normalized_source_text or payload.input_text,
                        source_manifest=source_manifest,
                        prompt_version=prompt_version,
                        uploaded_assets=uploaded_assets,
                    )
                    phase_timings_ms["single_pass_fallback"] = int((time.perf_counter() - fallback_started_at) * 1000)
                    extraction_mode = "single_pass_fallback"
                    if not normalized_source_text.strip():
                        normalized_source_text = str(payload.input_text or "").strip()
                        source_text_origin = "pasted_text" if normalized_source_text else None
            phase_timings_ms["total"] = sum(phase_timings_ms.values())
            add_checkpoint(
                trace,
                checkpoint="CP1_SIGNAL_READY",
                status="passed",
                details={
                    "schema": "content_signal.schema.json",
                    "source_length": len(payload.input_text),
                    "normalized_source_length": len(normalized_source_text),
                    "source_text_origin": source_text_origin or "",
                    "source_asset_count": source_asset_count,
                    "uploaded_asset_count": uploaded_asset_count,
                    "prompt_version": prompt_version,
                    "extraction_mode": extraction_mode,
                    "phase_timings_ms": phase_timings_ms,
                },
            )
            return {
                "status": "success",
                "content_signal": signal_data,
                "normalized_source_text": normalized_source_text,
                "source_text_origin": source_text_origin,
                "trace": trace.model_dump(),
            }
        except Exception as exc:
            print(f"Extraction error: {exc}")
            configured_version = os.getenv(
                "EXPLAINFLOW_SIGNAL_PROMPT_VERSION",
                SIGNAL_EXTRACTION_PROMPT_VERSION_DEFAULT,
            )
            prompt_version = configured_version.strip().lower()
            if prompt_version not in {"v1", "v2"}:
                prompt_version = SIGNAL_EXTRACTION_PROMPT_VERSION_DEFAULT
            add_checkpoint(
                trace,
                checkpoint="CP1_SIGNAL_READY",
                status="failed",
                details={
                    "error": str(exc),
                    "prompt_version": prompt_version,
                    "source_text_origin": payload.source_text_origin or "",
                    "source_asset_count": len(payload.source_manifest.assets) if payload.source_manifest is not None else 0,
                },
            )
            return {"status": "error", "message": str(exc), "trace": trace.model_dump()}
        finally:
            for file_name in uploaded_file_names:
                try:
                    await self.client.aio.files.delete(name=file_name)
                except Exception:
                    continue

    @staticmethod
    def _quick_grounded_claim_cards(
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
                GeminiStoryAgent._evidence_summary_bits(claim.get("evidence_snippets", []))
            )
            claim_cards.append(
                {
                    "claim_id": claim_id,
                    "claim_text": claim_text,
                    "evidence_summary": evidence_summary,
                }
            )
        return claim_cards

    @staticmethod
    def _enrich_quick_artifact_with_source_media(
        *,
        artifact: QuickArtifactSchema,
        content_signal: dict[str, Any] | None,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> QuickArtifactSchema:
        signal = content_signal or {}
        asset_lookup = GeminiStoryAgent._source_asset_lookup(source_manifest)
        evidence_by_claim, _, _ = GeminiStoryAgent._structured_evidence_refs(signal, source_manifest)
        if not asset_lookup or not evidence_by_claim:
            return artifact

        enriched = artifact.model_copy(deep=True)
        page_usage_counts: dict[tuple[str, int | None], int] = {}
        evidence_usage_counts: dict[str, int] = {}
        abstract_block_claimed = False

        def score(
            *,
            evidence: EvidenceRefSchema,
            allow_frontmatter: bool,
        ) -> float:
            asset = asset_lookup.get(evidence.asset_id)
            score_value = 0.0
            if evidence.modality == "video":
                score_value += 62.0
            elif evidence.modality == "audio":
                score_value += 42.0
            elif evidence.modality == "image":
                score_value += 28.0
            else:
                score_value += 24.0

            if evidence.start_ms is not None or evidence.end_ms is not None:
                score_value += 12.0
            if evidence.bbox_norm:
                score_value += 18.0
            if evidence.quote_text or evidence.transcript_text:
                score_value += 7.0
            if evidence.visual_context:
                score_value += 4.0

            page_index = GeminiStoryAgent._evidence_page_index(evidence, asset)
            if page_index is not None and page_index > 1:
                score_value += 8.0

            is_frontmatter = GeminiStoryAgent._is_frontmatter_pdf_evidence(evidence, asset)
            if is_frontmatter:
                score_value += 18.0 if allow_frontmatter else -34.0

            page_key = GeminiStoryAgent._evidence_page_key(evidence, asset)
            score_value -= page_usage_counts.get(page_key, 0) * 16.0
            score_value -= evidence_usage_counts.get(evidence.evidence_id, 0) * 26.0
            return score_value

        for block_index, block in enumerate(enriched.blocks):
            evidence_refs = list(block.evidence_refs)
            source_media = list(block.source_media)
            media_keys = {
                (
                    item.asset_id,
                    tuple(item.claim_refs),
                    tuple(item.evidence_refs),
                    item.start_ms,
                    item.end_ms,
                    item.page_index,
                    tuple(item.bbox_norm or []),
                )
                for item in source_media
            }
            allow_frontmatter = block_index == 0 and not abstract_block_claimed
            block_uses_frontmatter = False

            for claim_ref in block.claim_refs[:3]:
                ranked = sorted(
                    evidence_by_claim.get(claim_ref, []),
                    key=lambda evidence: (
                        score(evidence=evidence, allow_frontmatter=allow_frontmatter),
                        -(
                            GeminiStoryAgent._evidence_page_index(
                                evidence,
                                asset_lookup.get(evidence.asset_id),
                            )
                            or 0
                        ),
                    ),
                    reverse=True,
                )
                for evidence in ranked[:3]:
                    if evidence.evidence_id not in evidence_refs:
                        evidence_refs.append(evidence.evidence_id)

                    media_ref = GeminiStoryAgent._media_ref_for_evidence(
                        claim_ref=claim_ref,
                        evidence=evidence,
                    )
                    if media_ref is None or evidence.asset_id not in asset_lookup:
                        continue

                    media_key = (
                        media_ref.asset_id,
                        tuple(media_ref.claim_refs),
                        tuple(media_ref.evidence_refs),
                        media_ref.start_ms,
                        media_ref.end_ms,
                        media_ref.page_index,
                        tuple(media_ref.bbox_norm or []),
                    )
                    if media_key in media_keys:
                        continue

                    source_media.append(media_ref)
                    media_keys.add(media_key)
                    if GeminiStoryAgent._is_frontmatter_pdf_evidence(
                        evidence,
                        asset_lookup.get(evidence.asset_id),
                    ):
                        block_uses_frontmatter = True
                    break

                if len(source_media) >= 2:
                    break

            block.evidence_refs = evidence_refs[:6]
            block.source_media = source_media[:2]
            for evidence_id in block.evidence_refs:
                evidence_usage_counts[evidence_id] = evidence_usage_counts.get(evidence_id, 0) + 1
            for media in block.source_media:
                page_key = GeminiStoryAgent._media_page_key(media)
                page_usage_counts[page_key] = page_usage_counts.get(page_key, 0) + 1
            if block_uses_frontmatter:
                abstract_block_claimed = True

        return enriched

    @staticmethod
    def _quick_reel_media_key(
        media: SourceMediaRefSchema,
    ) -> tuple[str, int | None, int | None, int | None, tuple[float, ...]]:
        return (
            media.asset_id,
            media.start_ms,
            media.end_ms,
            media.page_index,
            tuple(float(value) for value in (media.bbox_norm or [])),
        )

    @staticmethod
    def _quick_reel_caption_text(text: str, *, fallback: str = "") -> str:
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

    @staticmethod
    def _select_quick_reel_media_for_block(
        *,
        block: QuickArtifactBlockSchema,
        used_media_keys: set[tuple[str, int | None, int | None, int | None, tuple[float, ...]]],
    ) -> SourceMediaRefSchema | None:
        if not block.source_media:
            return None

        block_claim_refs = {claim_ref for claim_ref in block.claim_refs if claim_ref}
        block_evidence_refs = {evidence_ref for evidence_ref in block.evidence_refs if evidence_ref}

        def rank(media: SourceMediaRefSchema) -> tuple[int, int, int, int, int]:
            media_key = GeminiStoryAgent._quick_reel_media_key(media)
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

    @staticmethod
    def _build_quick_reel_segment(
        *,
        artifact: QuickArtifactSchema,
        block: QuickArtifactBlockSchema,
        index: int,
        used_media_keys: set[tuple[str, int | None, int | None, int | None, tuple[float, ...]]],
    ) -> QuickReelSegmentSchema:
        primary_media = GeminiStoryAgent._select_quick_reel_media_for_block(
            block=block,
            used_media_keys=used_media_keys,
        )
        if primary_media is not None:
            used_media_keys.add(GeminiStoryAgent._quick_reel_media_key(primary_media))

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
            caption_text=GeminiStoryAgent._quick_reel_caption_text(
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

    @staticmethod
    def _build_quick_reel_from_artifact(
        *,
        artifact: QuickArtifactSchema,
        content_signal: dict[str, Any] | None,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> QuickReelSchema:
        used_media_keys: set[tuple[str, int | None, int | None, int | None, tuple[float, ...]]] = set()
        segments = [
            GeminiStoryAgent._build_quick_reel_segment(
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

    @staticmethod
    def _fallback_quick_artifact(
        *,
        topic: str,
        audience: str,
        tone: str,
        visual_mode: str,
        content_signal: dict[str, Any] | None = None,
    ) -> QuickArtifactSchema:
        tone_label = tone.strip() or "clear"
        claim_cards = GeminiStoryAgent._quick_grounded_claim_cards(content_signal)
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

    @staticmethod
    def _normalize_quick_artifact(
        artifact: QuickArtifactSchema,
        *,
        topic: str,
        audience: str,
        tone: str,
        visual_mode: str,
        content_signal: dict[str, Any] | None = None,
    ) -> QuickArtifactSchema:
        blocks = artifact.blocks[:4]
        fallback = GeminiStoryAgent._fallback_quick_artifact(
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
                    # Evidence/source media stay backend-owned so hallucinated asset ids and time ranges
                    # cannot leak from the LLM response into proof playback.
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

    async def _generate_quick_block_image(
        self,
        *,
        request: Request,
        topic: str,
        audience: str,
        tone: str,
        visual_mode: str,
        artifact: QuickArtifactSchema,
        block: QuickArtifactBlockSchema,
        content_signal: dict[str, Any] | None = None,
    ) -> str:
        claim_lookup = {
            card["claim_id"]: card
            for card in self._quick_grounded_claim_cards(content_signal)
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

        style_guide = self._style_guide_for_mode(visual_mode)
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

        response = await self.client.aio.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.6),
        )
        _, image_bytes = extract_parts_from_response(response)
        if not image_bytes:
            return ""
        return save_image_and_get_url(
            request=request,
            scene_id=f"{artifact.artifact_id}-{block.block_id}",
            image_bytes=image_bytes,
            prefix="quick_block",
        )

    async def _populate_quick_block_visuals(
        self,
        *,
        request: Request,
        topic: str,
        audience: str,
        tone: str,
        visual_mode: str,
        artifact: QuickArtifactSchema,
        content_signal: dict[str, Any] | None = None,
        only_block_ids: set[str] | None = None,
        force_block_ids: set[str] | None = None,
    ) -> QuickArtifactSchema:
        visualized = artifact.model_copy(deep=True)
        tasks: list[asyncio.Future[str] | asyncio.Task[str]] = []
        task_indices: list[int] = []
        targeted_block_ids = only_block_ids or {block.block_id for block in visualized.blocks}
        forced_block_ids = force_block_ids or set()
        for index, block in enumerate(visualized.blocks):
            if block.block_id not in targeted_block_ids:
                continue
            if block.source_media and block.block_id not in forced_block_ids:
                continue
            tasks.append(
                asyncio.create_task(
                    self._generate_quick_block_image(
                        request=request,
                        topic=topic,
                        audience=audience,
                        tone=tone,
                        visual_mode=visual_mode,
                        artifact=visualized,
                        block=block,
                        content_signal=content_signal,
                    )
                )
            )
            task_indices.append(index)
        if not tasks:
            return visualized
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for index, result in zip(task_indices, results):
            if isinstance(result, Exception) or not result:
                continue
            visualized.blocks[index] = visualized.blocks[index].model_copy(update={"image_url": result})
        return visualized

    @staticmethod
    def _quick_override_requests_visual_refresh(
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

    async def _generate_quick_hero_image(
        self,
        *,
        request: Request,
        topic: str,
        audience: str,
        tone: str,
        visual_mode: str,
        artifact: QuickArtifactSchema,
        content_signal: dict[str, Any] | None = None,
    ) -> str:
        claim_cards = self._quick_grounded_claim_cards(content_signal)
        claim_block = ""
        if claim_cards:
            claim_block = "SOURCE CLAIMS:\n" + "\n".join(
                f"- {card['claim_text']}" for card in claim_cards[:4]
            ) + "\n\n"

        style_guide = self._style_guide_for_mode(visual_mode)
        prompt = (
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

        response = await self.client.aio.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.6),
        )
        _, image_bytes = extract_parts_from_response(response)
        if not image_bytes:
            return ""
        return save_image_and_get_url(
            request=request,
            scene_id=artifact.artifact_id,
            image_bytes=image_bytes,
            prefix="quick_hero",
        )

    async def generate_quick_artifact(self, payload: QuickArtifactRequest, *, request: Request) -> dict[str, Any]:
        topic = payload.topic.strip()
        audience = payload.audience.strip() or "general audience"
        tone = payload.tone.strip()
        visual_mode = payload.visual_mode.strip() or "illustration"
        if not topic:
            return {"status": "error", "message": "Provide a topic before generating a quick artifact."}

        style_guide = self._style_guide_for_mode(visual_mode)
        content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
        claim_cards = self._quick_grounded_claim_cards(content_signal)
        source_excerpt = (payload.normalized_source_text or payload.source_text or "").strip()[:3200]
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
        prompt = (
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

        try:
            response = await self.client.aio.models.generate_content(
                model=self._quick_artifact_model(),
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    response_mime_type="application/json",
                    response_schema=QuickArtifactSchema,
                ),
            )
            artifact = QuickArtifactSchema.model_validate_json(response.text)
        except Exception:
            artifact = self._fallback_quick_artifact(
                topic=topic,
                audience=audience,
                tone=tone,
                visual_mode=visual_mode,
                content_signal=content_signal,
            )

        normalized = self._normalize_quick_artifact(
            artifact,
            topic=topic,
            audience=audience,
            tone=tone,
            visual_mode=visual_mode,
            content_signal=content_signal,
        )
        normalized = self._enrich_quick_artifact_with_source_media(
            artifact=normalized,
            content_signal=content_signal,
            source_manifest=payload.source_manifest,
        )
        normalized = await self._populate_quick_block_visuals(
            request=request,
            topic=topic,
            audience=audience,
            tone=tone,
            visual_mode=visual_mode,
            artifact=normalized,
            content_signal=content_signal,
        )
        try:
            hero_image_url = await self._generate_quick_hero_image(
                request=request,
                topic=topic,
                audience=audience,
                tone=tone,
                visual_mode=visual_mode,
                artifact=normalized,
                content_signal=content_signal,
            )
        except Exception:
            hero_image_url = ""
        if hero_image_url:
            normalized = normalized.model_copy(update={"hero_image_url": hero_image_url})
        return {"status": "success", "artifact": normalized.model_dump()}

    async def generate_quick_reel(self, payload: QuickReelRequest) -> dict[str, Any]:
        artifact = QuickArtifactSchema.model_validate(payload.artifact)
        if not artifact.blocks:
            return {"status": "error", "message": "Provide a quick artifact before generating a proof reel."}

        content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
        reel = self._build_quick_reel_from_artifact(
            artifact=artifact,
            content_signal=content_signal,
            source_manifest=payload.source_manifest,
        )
        return {
            "status": "success",
            "artifact": artifact.model_copy(update={"reel": reel}).model_dump(),
        }

    async def regenerate_quick_block(self, payload: QuickBlockOverrideRequest, *, request: Request) -> dict[str, Any]:
        topic = payload.topic.strip()
        audience = payload.audience.strip() or "general audience"
        tone = payload.tone.strip()
        visual_mode = payload.visual_mode.strip() or "illustration"
        instruction = payload.instruction.strip()
        if not topic or not instruction:
            return {"status": "error", "message": "Provide a topic and a direction note before regenerating a block."}

        artifact = QuickArtifactSchema.model_validate(payload.artifact)
        target_block = next((block for block in artifact.blocks if block.block_id == payload.block_id), None)
        if target_block is None:
            return {"status": "error", "message": f"Unknown block id: {payload.block_id}"}
        content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
        claim_cards = self._quick_grounded_claim_cards(content_signal)

        companion_blocks = [
            {
                "block_id": block.block_id,
                "label": block.label,
                "title": block.title,
                "emphasis": block.emphasis,
            }
            for block in artifact.blocks
            if block.block_id != payload.block_id
        ]
        prompt = (
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

        try:
            response = await self.client.aio.models.generate_content(
                model=self._quick_artifact_model(),
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

        normalized_block = QuickArtifactBlockSchema(
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
        force_visual_refresh = self._quick_override_requests_visual_refresh(
            instruction=instruction,
            original_block=target_block,
            updated_block=normalized_block,
        )
        visualized_block = self._enrich_quick_artifact_with_source_media(
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
        visualized_block = await self._populate_quick_block_visuals(
            request=request,
            topic=topic,
            audience=audience,
            tone=tone,
            visual_mode=visual_mode,
            artifact=visualized_block,
            content_signal=content_signal,
            force_block_ids={target_block.block_id} if force_visual_refresh else None,
        )
        return {"status": "success", "block": visualized_block.blocks[0].model_dump()}

    async def regenerate_quick_artifact(self, payload: QuickArtifactOverrideRequest, *, request: Request) -> dict[str, Any]:
        topic = payload.topic.strip()
        audience = payload.audience.strip() or "general audience"
        tone = payload.tone.strip()
        visual_mode = payload.visual_mode.strip() or "illustration"
        instruction = payload.instruction.strip()
        if not topic or not instruction:
            return {"status": "error", "message": "Provide a topic and a direction note before regenerating the quick artifact."}

        artifact = QuickArtifactSchema.model_validate(payload.artifact)
        content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
        claim_cards = self._quick_grounded_claim_cards(content_signal)
        anchor_block_id = (payload.anchor_block_id or "").strip() or None
        anchor_index = next((idx for idx, block in enumerate(artifact.blocks) if block.block_id == anchor_block_id), 0 if anchor_block_id is None else -1)
        if anchor_index < 0:
            return {"status": "error", "message": f"Unknown anchor block id: {anchor_block_id}"}

        preserved_blocks = [block.model_dump() for block in artifact.blocks[:anchor_index]]
        editable_blocks = [block.model_dump() for block in artifact.blocks[anchor_index:]]
        prompt = (
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

        try:
            response = await self.client.aio.models.generate_content(
                model=self._quick_artifact_model(),
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

        normalized = self._normalize_quick_artifact(
            updated_artifact,
            topic=topic,
            audience=audience,
            tone=tone,
            visual_mode=visual_mode,
            content_signal=content_signal,
        )

        if anchor_index > 0:
            preserved = artifact.blocks[:anchor_index]
            regenerated = normalized.blocks[anchor_index:]
            normalized = QuickArtifactSchema(
                artifact_id=artifact.artifact_id,
                title=artifact.title,
                subtitle=artifact.subtitle,
                summary=artifact.summary,
                visual_style=normalized.visual_style,
                hero_direction=artifact.hero_direction,
                blocks=[*preserved, *regenerated],
            )
        else:
            normalized = QuickArtifactSchema(
                artifact_id=artifact.artifact_id,
                title=normalized.title,
                subtitle=normalized.subtitle,
                summary=normalized.summary,
                visual_style=normalized.visual_style,
                hero_direction=normalized.hero_direction,
                blocks=normalized.blocks,
            )

        normalized = self._enrich_quick_artifact_with_source_media(
            artifact=normalized,
            content_signal=content_signal,
            source_manifest=payload.source_manifest,
        )
        normalized = await self._populate_quick_block_visuals(
            request=request,
            topic=topic,
            audience=audience,
            tone=tone,
            visual_mode=visual_mode,
            artifact=normalized,
            content_signal=content_signal,
            only_block_ids={block.block_id for block in normalized.blocks[anchor_index:]} if anchor_index > 0 else None,
        )
        try:
            hero_image_url = await self._generate_quick_hero_image(
                request=request,
                topic=topic,
                audience=audience,
                tone=tone,
                visual_mode=visual_mode,
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

    async def generate_stream_events(
        self,
        *,
        request: Request,
        topic: str,
        audience: str,
        tone: str,
        visual_mode: str = "illustration",
    ) -> AsyncIterator[dict[str, str]]:
        run_id = self._new_run_id("interleaved-run")
        artifact_scope = self._resolve_artifact_scope(
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

        style_guide = self._style_guide_for_mode(visual_mode)
        planning_prompt = (
            f"Create a 4-scene outline for a visual explainer about '{topic}'. "
            f"Target audience: {audience}. Tone: {tone or 'clear and engaging'}. "
            "You MUST generate EXACTLY 4 scenes.\n\n"
            f"Visual rule: {style_guide}"
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
            plan_response = await self.client.aio.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=planning_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=OutlineSchema,
                ),
            )
            parsed_outline = OutlineSchema.model_validate_json(plan_response.text)
            scenes = parsed_outline.scenes[:4]

            cp1 = add_checkpoint(
                trace,
                checkpoint="CP1_SIGNAL_READY",
                status="passed",
                details={"source": "quick_prompt_planning", "planned_scenes": len(scenes)},
            )
            yield build_checkpoint_event(trace, cp1)

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

                scene_id = normalized_scene_id(scene.scene_id, idx)
                title = scene.title or f"Scene {idx}"
                narration_focus = scene.narration_focus or f"Explain key point {idx}."
                visual_prompt = scene.visual_prompt or ""
                claim_refs = [ref for ref in scene.claim_refs if ref]
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
                    {
                        "scene_id": scene_id,
                        "title": title,
                        "claim_refs": claim_refs,
                        "trace": scene_trace_payload,
                    },
                )

                scene_result: dict[str, Any] = {}

                async for event in self._stream_scene_assets(
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

            traceability = self._claim_traceability_summary(
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
            message = self._friendly_quota_error_message() if self._is_resource_exhausted(exc) else str(exc)
            yield build_sse_event("error", {"error": message, "trace": trace.model_dump()})

    async def generate_stream_advanced_events(
        self,
        *,
        request: Request,
        payload: AdvancedStreamRequest,
    ) -> AsyncIterator[dict[str, str]]:
        content_signal = payload.content_signal
        render_profile = payload.render_profile
        run_id = self._new_run_id("advanced-run")
        artifact_scope = self._resolve_artifact_scope(
            requested_scope=payload.artifact_scope,
            render_profile=render_profile,
            default_scope=["story_cards", "voiceover", "social_caption"],
        )
        trace = init_trace_envelope(
            trace_id=f"trace-{uuid4().hex[:12]}",
            run_id=run_id,
            flow="advanced_stream",
            artifact_scope=artifact_scope,
        )

        approved_script_pack_raw = payload.script_pack
        approved_script_pack: ScriptPack | None = None
        if isinstance(approved_script_pack_raw, dict):
            try:
                approved_script_pack = ScriptPack.model_validate(approved_script_pack_raw)
            except Exception:
                approved_script_pack = None

        has_signal = bool(
            content_signal.get("thesis")
            or content_signal.get("key_claims")
            or content_signal.get("narrative_beats")
        )
        cp1 = add_checkpoint(
            trace,
            checkpoint="CP1_SIGNAL_READY",
            status="passed" if has_signal else "failed",
            details={"source": "content_signal_payload", "has_signal": has_signal},
        )
        yield build_checkpoint_event(trace, cp1)
        if not has_signal:
            yield build_sse_event(
                "error",
                {
                    "error": "Signal is missing. Run extraction and provide content_signal before generation.",
                    "trace": trace.model_dump(),
                },
            )
            return

        cp2 = add_checkpoint(
            trace,
            checkpoint="CP2_ARTIFACTS_LOCKED",
            status="passed",
            details={"artifact_scope": artifact_scope},
        )
        yield build_checkpoint_event(trace, cp2)

        visual_mode = render_profile.get("visual_mode", "illustration")
        audience_cfg = render_profile.get("audience", {})
        audience_level = str(audience_cfg.get("level", "beginner")).lower()
        audience_persona = str(audience_cfg.get("persona", "General audience")).strip()
        domain_context = str(audience_cfg.get("domain_context", "")).strip()
        taste_bar = str(audience_cfg.get("taste_bar", "standard")).lower()
        must_include = [
            str(item).strip()
            for item in audience_cfg.get("must_include", [])
            if isinstance(item, str) and str(item).strip()
        ][:8]
        must_avoid = [
            str(item).strip()
            for item in audience_cfg.get("must_avoid", [])
            if isinstance(item, str) and str(item).strip()
        ][:8]
        goal = render_profile.get("goal", "teach")
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

        cp3 = add_checkpoint(
            trace,
            checkpoint="CP3_RENDER_LOCKED",
            status="passed",
            details={"visual_mode": visual_mode, "goal": str(render_profile.get("goal", "teach"))},
        )
        yield build_checkpoint_event(trace, cp3)

        thesis = content_signal.get("thesis", {}).get("one_liner", "A generic topic")
        claim_ids = [
            str(claim.get("claim_id")).strip()
            for claim in content_signal.get("key_claims", [])
            if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
        ]
        claim_text_lookup = {
            str(claim.get("claim_id")).strip(): str(claim.get("claim_text") or claim.get("content") or "").strip()
            for claim in content_signal.get("key_claims", [])
            if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
        }
        claim_evidence_lookup = {
            str(claim.get("claim_id")).strip(): self._evidence_summary_bits(
                claim.get("evidence_snippets", []) if isinstance(claim.get("evidence_snippets"), list) else []
            )
            for claim in content_signal.get("key_claims", [])
            if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
        }
        audience_descriptor = f"{audience_persona} ({audience_level})"
        if domain_context:
            audience_descriptor += f" in {domain_context}"

        scene_evidence_map: dict[str, list[str]] = {}
        evidence_ids: list[str] = []

        try:
            if approved_script_pack is not None and approved_script_pack.scenes:
                script_pack = approved_script_pack
                yield build_sse_event(
                    "status",
                    {
                        "message": "Using approved script pack. Starting scene generation...",
                        "trace": trace_meta(trace, checkpoint="CP4_SCRIPT_LOCKED"),
                    },
                )
            else:
                script_pack, _, planner_qa_summary = await self._plan_script_pack(
                    source_text=payload.source_text,
                    normalized_source_text=payload.normalized_source_text,
                    content_signal=content_signal,
                    render_profile=render_profile,
                    artifact_scope=artifact_scope,
                )
                planner_qa_payload = planner_qa_summary.model_dump()

            script_pack, scene_evidence_map, evidence_ids = self._enrich_script_pack_with_source_media(
                script_pack=script_pack,
                content_signal=content_signal,
                source_manifest=payload.source_manifest,
            )
            
            if approved_script_pack is not None and approved_script_pack.scenes:
                planner_qa_payload = None

            yield build_sse_event(
                "script_pack_ready",
                {
                    "script_pack": script_pack.model_dump(),
                    **({"planner_qa_summary": planner_qa_payload} if planner_qa_payload else {}),
                    "trace": trace_meta(trace, checkpoint="CP4_SCRIPT_LOCKED"),
                },
            )

            cp4 = add_checkpoint(
                trace,
                checkpoint="CP4_SCRIPT_LOCKED",
                status="passed",
                details={"scene_count": script_pack.scene_count, "approved_script_pack": approved_script_pack is not None},
            )
            yield build_checkpoint_event(trace, cp4)

            yield build_sse_event(
                "scene_queue_ready",
                {
                    "scenes": [
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
                    ],
                    "optimized_count": script_pack.scene_count,
                    "trace": trace_meta(trace, checkpoint="CP4_SCRIPT_LOCKED"),
                },
            )

            continuity_memory: list[str] = []
            scene_claim_map: dict[str, list[str]] = {}
            prepared_scenes: list[dict[str, Any]] = []

            for scene in script_pack.scenes:
                if await request.is_disconnected():
                    return

                scene_id = scene.scene_id
                title = scene.title
                scene_trace_id = f"{trace.trace_id}-{scene_id}-{uuid4().hex[:8]}"
                claim_refs = [claim_ref for claim_ref in scene.claim_refs if claim_ref]
                scene_claim_map[scene_id] = claim_refs
                evidence_refs = [evidence_ref for evidence_ref in scene.evidence_refs if evidence_ref]
                scene_evidence_map[scene_id] = evidence_refs
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
                media_asset_ids = [item.asset_id for item in scene.source_media if item.asset_id]
                add_or_update_scene_trace(
                    trace,
                    scene_id=scene_id,
                    scene_trace_id=scene_trace_id,
                    claim_refs=claim_refs,
                    evidence_refs=evidence_refs,
                    render_strategy=scene.render_strategy,
                    media_asset_ids=media_asset_ids,
                )
                scene_trace_payload = trace_meta(trace, scene_trace_id=scene_trace_id)
                prepared_scenes.append(
                    {
                        "scene": scene,
                        "scene_id": scene_id,
                        "title": title,
                        "scene_trace_id": scene_trace_id,
                        "scene_trace_payload": scene_trace_payload,
                        "claim_refs": claim_refs,
                        "evidence_refs": evidence_refs,
                        "claim_text_snippets": claim_text_snippets,
                        "evidence_text_snippets": evidence_text_snippets,
                    }
                )

            if prepared_scenes:
                first_spec = prepared_scenes[0]
                first_scene = first_spec["scene"]
                first_scene_id = str(first_spec["scene_id"])
                first_scene_trace_id = str(first_spec["scene_trace_id"])
                first_scene_trace_payload = dict(first_spec["scene_trace_payload"])
                first_title = str(first_spec["title"])
                first_claim_refs = list(first_spec["claim_refs"])
                first_evidence_refs = list(first_spec["evidence_refs"])

                yield build_sse_event(
                    "scene_start",
                    {
                        "scene_id": first_scene_id,
                        "title": first_title,
                        "claim_refs": first_claim_refs,
                        "evidence_refs": first_evidence_refs,
                        "render_strategy": first_scene.render_strategy,
                        "source_media": [item.model_dump() for item in first_scene.source_media],
                        "trace": first_scene_trace_payload,
                    },
                )

                for source_media_payload in self._resolve_source_media_payloads(
                    request=request,
                    scene_id=first_scene_id,
                    source_media=first_scene.source_media,
                    source_manifest=payload.source_manifest,
                ):
                    source_media_payload["trace"] = first_scene_trace_payload
                    yield build_sse_event("source_media_ready", source_media_payload)

                first_retries_used = 0
                first_qa_result: dict[str, Any] = {
                    "scene_id": first_scene_id,
                    "status": "WARN",
                    "score": 0.0,
                    "reasons": ["Quality checks not executed."],
                    "attempt": 1,
                    "word_count": 0,
                }
                first_scene_result: dict[str, Any] = {}
                first_retry_reason_constraints: list[str] = []

                for attempt_index in range(2):
                    first_scene_result = {}
                    active_continuity = (continuity_memory[-3:] + first_scene.continuity_refs)[-6:]
                    attempt_constraints = list(first_scene.acceptance_checks)
                    if first_retry_reason_constraints:
                        attempt_constraints.append(
                            f"Fix these QA issues from previous attempt: {'; '.join(first_retry_reason_constraints[:3])}."
                        )

                    if attempt_index > 0:
                        yield build_sse_event(
                            "scene_retry_reset",
                            {
                                "scene_id": first_scene_id,
                                "retry_index": attempt_index,
                                "trace": first_scene_trace_payload,
                            },
                        )

                    async for event in self._stream_scene_assets(
                        request=request,
                        scene_id=first_scene_id,
                        topic=thesis,
                        audience=audience_descriptor,
                        tone=goal,
                        scene_title=first_title,
                        narration_focus=first_scene.narration_focus,
                        scene_goal=first_scene.scene_goal,
                        style_guide=style_guide,
                        visual_prompt=first_scene.visual_prompt,
                        image_prefix="advanced_interleaved",
                        audio_prefix="advanced_audio",
                        artifact_type=script_pack.artifact_type,
                        scene_mode=first_scene.scene_mode,
                        layout_template=first_scene.layout_template,
                        focal_subject=first_scene.focal_subject,
                        visual_hierarchy=first_scene.visual_hierarchy,
                        modules=first_scene.modules,
                        claim_refs=first_scene.claim_refs,
                        claim_text_snippets=list(first_spec["claim_text_snippets"]),
                        evidence_text_snippets=list(first_spec["evidence_text_snippets"]),
                        crop_safe_regions=first_scene.crop_safe_regions,
                        continuity_hints=active_continuity,
                        extra_constraints=attempt_constraints,
                        result_collector=first_scene_result,
                        trace_payload=first_scene_trace_payload,
                    ):
                        yield event

                    first_qa_result = evaluate_scene_quality(
                        scene=first_scene,
                        generated_text=str(first_scene_result.get("text", "")),
                        image_url=str(first_scene_result.get("image_url", "")),
                        must_include=must_include,
                        must_avoid=must_avoid,
                        continuity_hints=active_continuity,
                        attempt=attempt_index + 1,
                        artifact_type=script_pack.artifact_type,
                    )
                    add_or_update_scene_trace(
                        trace,
                        scene_id=first_scene_id,
                        scene_trace_id=first_scene_trace_id,
                        qa_result=first_qa_result,
                    )
                    yield build_sse_event(
                        "qa_status",
                        {
                            **first_qa_result,
                            "trace": first_scene_trace_payload,
                        },
                    )

                    if first_qa_result["status"] != "FAIL":
                        break

                    if attempt_index == 0:
                        first_retry_reason_constraints = list(first_qa_result["reasons"])
                        first_retries_used = 1
                        yield build_sse_event(
                            "qa_retry",
                            {
                                "scene_id": first_scene_id,
                                "retry_index": 1,
                                "reasons": first_qa_result["reasons"],
                                "trace": first_scene_trace_payload,
                            },
                        )

                first_continuity_tokens = extract_anchor_terms(str(first_scene_result.get("text", "")), limit=4)
                if first_continuity_tokens:
                    continuity_memory.append(f"{first_title}: {', '.join(first_continuity_tokens)}")
                    continuity_memory = continuity_memory[-8:]
                add_or_update_scene_trace(
                    trace,
                    scene_id=first_scene_id,
                    scene_trace_id=first_scene_trace_id,
                    retries_used=first_retries_used,
                    word_count=int(first_scene_result.get("word_count", 0)),
                )

                yield build_sse_event(
                    "scene_done",
                    {
                        "scene_id": first_scene_id,
                        "qa_status": first_qa_result["status"],
                        "auto_retries": first_retries_used,
                        "trace": first_scene_trace_payload,
                    },
                )

            remaining_scenes = prepared_scenes[1:]
            scene_concurrency = self._advanced_scene_concurrency()

            for batch_start in range(0, len(remaining_scenes), scene_concurrency):
                if await request.is_disconnected():
                    return

                batch = remaining_scenes[batch_start : batch_start + scene_concurrency]
                continuity_snapshot = continuity_memory[-3:]
                batch_tasks = [
                    asyncio.create_task(
                        self._execute_buffered_advanced_scene(
                            request=request,
                            scene=spec["scene"],
                            thesis=thesis,
                            audience_descriptor=audience_descriptor,
                            goal=goal,
                            style_guide=style_guide,
                            script_pack=script_pack,
                            source_manifest=payload.source_manifest,
                            must_include=must_include,
                            must_avoid=must_avoid,
                            claim_text_snippets=list(spec["claim_text_snippets"]),
                            evidence_text_snippets=list(spec["evidence_text_snippets"]),
                            active_continuity=(continuity_snapshot + spec["scene"].continuity_refs)[-6:],
                            scene_trace_payload=dict(spec["scene_trace_payload"]),
                        )
                    )
                    for spec in batch
                ]
                batch_results = await asyncio.gather(*batch_tasks)

                for spec, buffered_result in zip(batch, batch_results):
                    add_or_update_scene_trace(
                        trace,
                        scene_id=buffered_result.scene_id,
                        scene_trace_id=buffered_result.scene_trace_id,
                        qa_result=buffered_result.qa_result,
                    )
                    add_or_update_scene_trace(
                        trace,
                        scene_id=buffered_result.scene_id,
                        scene_trace_id=buffered_result.scene_trace_id,
                        retries_used=buffered_result.retries_used,
                        word_count=buffered_result.word_count,
                    )

                    for event in buffered_result.events:
                        yield event

                    if buffered_result.continuity_tokens:
                        continuity_memory.append(
                            f"{spec['title']}: {', '.join(buffered_result.continuity_tokens)}"
                        )
                        continuity_memory = continuity_memory[-8:]

            cp5 = add_checkpoint(
                trace,
                checkpoint="CP5_STREAM_COMPLETE",
                status="passed",
                details={"scene_count": script_pack.scene_count},
            )
            yield build_checkpoint_event(trace, cp5)

            traceability = self._claim_traceability_summary(
                claim_ids=claim_ids,
                scene_claim_map=scene_claim_map,
                evidence_ids=evidence_ids,
                scene_evidence_map=scene_evidence_map,
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
            print(f"Error in advanced stream: {exc}")
            cp4_passed = any(
                checkpoint.checkpoint == "CP4_SCRIPT_LOCKED" and checkpoint.status == "passed"
                for checkpoint in trace.checkpoints
            )
            failed_checkpoint = "CP5_STREAM_COMPLETE" if cp4_passed else "CP4_SCRIPT_LOCKED"
            failed_record = add_checkpoint(
                trace,
                checkpoint=failed_checkpoint,
                status="failed",
                details={"error": str(exc)},
            )
            yield build_checkpoint_event(trace, failed_record)
            message = self._friendly_quota_error_message() if self._is_resource_exhausted(exc) else str(exc)
            yield build_sse_event("error", {"error": message, "trace": trace.model_dump()})

    async def generate_script_pack_advanced(self, payload: ScriptPackRequest) -> dict[str, Any]:
        content_signal = payload.content_signal
        render_profile = payload.render_profile
        run_id = self._new_run_id("script-pack-run")
        artifact_scope = self._resolve_artifact_scope(
            requested_scope=payload.artifact_scope,
            render_profile=render_profile,
            default_scope=["story_cards", "voiceover"],
        )
        trace = init_trace_envelope(
            trace_id=f"trace-{uuid4().hex[:12]}",
            run_id=run_id,
            flow="script_pack_only",
            artifact_scope=artifact_scope,
        )

        has_signal = bool(
            content_signal.get("thesis")
            or content_signal.get("key_claims")
            or content_signal.get("narrative_beats")
        )
        add_checkpoint(
            trace,
            checkpoint="CP1_SIGNAL_READY",
            status="passed" if has_signal else "failed",
            details={"source": "content_signal_payload", "has_signal": has_signal},
        )
        if not has_signal:
            return {
                "status": "error",
                "message": "Signal is missing. Run extraction and provide content_signal before script planning.",
                "trace": trace.model_dump(),
            }

        add_checkpoint(
            trace,
            checkpoint="CP2_ARTIFACTS_LOCKED",
            status="passed",
            details={"artifact_scope": artifact_scope},
        )
        add_checkpoint(
            trace,
            checkpoint="CP3_RENDER_LOCKED",
            status="passed",
            details={"density": str(render_profile.get("density", "standard"))},
        )

        try:
            script_pack, _, planner_qa_summary = await self._plan_script_pack(
                source_text=payload.source_text,
                normalized_source_text=payload.normalized_source_text,
                content_signal=content_signal,
                render_profile=render_profile,
                artifact_scope=artifact_scope,
            )
            script_pack, scene_evidence_map, evidence_ids = self._enrich_script_pack_with_source_media(
                script_pack=script_pack,
                content_signal=content_signal,
                source_manifest=payload.source_manifest,
            )
            claim_ids = [
                str(claim.get("claim_id")).strip()
                for claim in content_signal.get("key_claims", [])
                if isinstance(claim, dict) and str(claim.get("claim_id", "")).strip()
            ]
            claim_traceability = self._claim_traceability_summary(
                claim_ids=claim_ids,
                scene_claim_map={
                    scene.scene_id: [claim_ref for claim_ref in scene.claim_refs if claim_ref]
                    for scene in script_pack.scenes
                },
                evidence_ids=evidence_ids,
                scene_evidence_map=scene_evidence_map,
            )
            add_checkpoint(
                trace,
                checkpoint="CP4_SCRIPT_LOCKED",
                status="passed",
                details={"scene_count": script_pack.scene_count},
            )
            return {
                "status": "success",
                "script_pack": script_pack.model_dump(),
                "planner_qa_summary": planner_qa_summary.model_dump(),
                "trace": trace.model_dump(),
                "claim_traceability": claim_traceability,
            }
        except Exception as exc:
            print(f"Error generating script pack: {exc}")
            add_checkpoint(
                trace,
                checkpoint="CP4_SCRIPT_LOCKED",
                status="failed",
                details={"error": str(exc)},
            )
            message = self._friendly_quota_error_message() if self._is_resource_exhausted(exc) else str(exc)
            return {"status": "error", "message": message, "trace": trace.model_dump()}

    async def regenerate_scene(
        self,
        payload: RegenerateSceneRequest,
        request: Request,
    ) -> dict[str, Any]:
        run_id = self._new_run_id("regen-run")
        trace = init_trace_envelope(
            trace_id=f"trace-{uuid4().hex[:12]}",
            run_id=run_id,
            flow="scene_regeneration",
            artifact_scope=["story_cards", "voiceover"],
        )
        scene_id = payload.scene_id
        current_text = payload.current_text
        instruction = payload.instruction
        visual_mode = payload.visual_mode
        scene_trace_id = f"{trace.trace_id}-{scene_id}-{uuid4().hex[:8]}"

        try:
            style_guide = self._style_guide_for_mode(visual_mode)
            regen_prompt = (
                f"Regenerate scene {scene_id} with this instruction: {instruction}\n\n"
                f"Original text context: {current_text}\n\n"
                "Requirements:\n"
                "1) Return updated narration text first (no labels or markdown).\n"
                "2) Then return one high-quality inline image for that scene. "
                "The image MUST accurately depict any specific scientific or historical details mentioned in the text.\n"
                f"3) Follow this visual style guide: {style_guide}"
            )

            response = await self.client.aio.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=regen_prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )
            updated_text, image_bytes = extract_parts_from_response(response)

            image_url = ""
            if image_bytes:
                image_url = save_image_and_get_url(
                    request=request,
                    scene_id=scene_id,
                    image_bytes=image_bytes,
                    prefix="regen",
                )

            audio_url = generate_audio_and_get_url(
                request=request,
                scene_id=scene_id,
                text=updated_text,
                prefix="regen_audio",
            )
            add_or_update_scene_trace(
                trace,
                scene_id=scene_id,
                scene_trace_id=scene_trace_id,
                word_count=len(re.findall(r"\b[\w'-]+\b", updated_text)),
            )
            add_checkpoint(
                trace,
                checkpoint="CP5_STREAM_COMPLETE",
                status="passed",
                details={"mode": "scene_regen"},
            )

            return {
                "status": "success",
                "scene_id": scene_id,
                "text": updated_text,
                "imageUrl": image_url,
                "audioUrl": audio_url,
                "trace": trace.model_dump(),
            }
        except Exception as exc:
            print(f"Regeneration error: {exc}")
            add_checkpoint(
                trace,
                checkpoint="CP5_STREAM_COMPLETE",
                status="failed",
                details={"mode": "scene_regen", "error": str(exc)},
            )
            return {"status": "error", "message": str(exc), "trace": trace.model_dump()}
