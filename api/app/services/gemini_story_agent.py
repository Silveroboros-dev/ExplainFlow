import asyncio
from dataclasses import dataclass
import json
import math
import os
import re
import time
from typing import Any, AsyncIterator, Literal
from uuid import uuid4

from fastapi import Request
from google.genai import types

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
    QuickVideoRequest,
    RegenerateSceneRequest,
    SourceAssetSchema,
    SourceManifestSchema,
    SourceMediaRefSchema,
    SceneModuleSchema,
    ScriptPack,
    ScriptPackRequest,
    ScriptPackScene,
    SignalExtractionRequest,
    WorkflowSceneRegenerateRequest,
)
from app.services.audio_pipeline import generate_audio_and_get_url
from app.services.image_pipeline import (
    asset_path_from_reference,
    build_thumbnail_cover_cues,
    compose_thumbnail_cover_and_get_url,
    save_image_and_get_url,
)
from app.services.interleaved_parser import (
    append_text_part,
    evaluate_scene_quality,
    extract_anchor_terms,
    extract_parts_from_chunk,
    extract_parts_from_response,
)
from app.services.source_ingest import (
    best_effort_manifest_text,
    resolve_pdf_proof_locator,
    validate_video_manifest_constraints,
)
from app.services.story_agent_extraction import (
    build_creative_signal_prompt,
    build_fallback_narrative_beats,
    build_fallback_visual_candidates,
    build_signal_extraction_prompt,
    build_source_text_recovery_prompt,
    build_structural_signal_prompt,
    build_transcript_normalization_prompt,
    merge_signal_extraction_passes,
    should_use_text_backed_fast_extraction,
    transcript_needs_normalization,
)
from app.services.story_agent_extraction_runtime import (
    build_signal_extraction_contents,
    extract_signal_creative,
    extract_signal_one_pass,
    extract_signal_structural,
    normalize_transcript_source_text,
    recover_normalized_source_text,
)
from app.services.story_agent_planner import (
    ArtifactPlanningPolicy,
    ForwardPullSchema,
    PlannerEnrichmentContext,
    PlannerValidationReport,
    SalienceAssessmentSchema,
    best_effort_salience_summary,
    build_enrichment_context,
    build_forward_pull_prompt,
    build_planner_qa_summary,
    build_replan_directives,
    build_salience_prompt,
    build_script_pack_prompt,
    derive_scene_count,
    fallback_scene_plan,
    forward_pull_guidance,
    outline_to_script_pack,
    planner_source_text,
    repair_script_pack_from_enrichments,
    resolve_artifact_policy,
    resolve_planner_artifact_type,
    salience_candidates,
    validate_script_pack_against_enrichments,
)
from app.services.story_agent_advanced_stream import (
    build_advanced_scene_queue_payloads,
    build_scene_attempt_constraints,
    build_scene_start_payload,
    default_scene_qa_result,
    prepare_advanced_scene_spec,
    update_scene_continuity_memory,
    active_scene_continuity,
)
from app.services.story_agent_scene_generation import (
    build_claim_grounding_maps,
    build_regenerate_scene_prompt,
    build_render_profile_scene_context,
    build_scene_grounding_snippets,
    build_stream_scene_prompt,
    continuity_hints_from_scene_context,
    style_guide_for_mode,
    workflow_scene_override_constraints,
)
from app.services.story_agent_quick import (
    build_quick_scene_start_payload,
    build_quick_stream_planning_prompt,
    normalize_quick_scene_identity,
    normalize_quick_stream_scenes,
    quick_grounded_claim_cards,
)
from app.services.story_agent_source_media import (
    asset_duration_ms,
    build_source_media_warning_payload,
    claim_has_non_frontmatter_media,
    coerce_evidence_time_range_ms,
    coerce_timecode_ms,
    effective_evidence_media_modality,
    enrich_script_pack_with_source_media,
    evidence_page_index,
    evidence_page_key,
    evidence_summary_bits,
    evidence_text_blob,
    is_frontmatter_pdf_evidence,
    is_frontmatter_pdf_media,
    is_youtube_video_asset,
    media_page_key,
    media_ref_for_evidence,
    merge_source_media_item,
    merge_source_media_list,
    resolve_source_media_payloads,
    richer_optional_text,
    scene_is_opener_or_hook,
    should_exclude_frontmatter_evidence,
    should_exclude_frontmatter_media,
    should_upload_source_assets_for_extraction,
    sort_claim_evidence_for_scene,
    source_asset_lookup,
    source_manifest_for_extraction,
    source_manifest_summary,
    source_media_merge_key,
    structured_evidence_refs,
    transcript_only_video_mode,
)
from app.services.video_pipeline import build_quick_video

SIGNAL_EXTRACTION_PROMPT_VERSION_DEFAULT = "v2"
SIGNAL_STRUCTURAL_MODEL_DEFAULT = "gemini-3.1-pro-preview"
SIGNAL_CREATIVE_MODEL_DEFAULT = "gemini-3.1-pro-preview"
SIGNAL_SOURCE_TEXT_MODEL_DEFAULT = "gemini-3-flash-preview"
PLANNER_PRECOMPUTE_MODEL_DEFAULT = "gemini-3-flash-preview"
ADVANCED_SCENE_CONCURRENCY_DEFAULT = 2
QUICK_ARTIFACT_MODEL_DEFAULT = "gemini-3-flash-preview"

@dataclass(frozen=True)
class UploadedSourceAssets:
    parts: tuple[Any, ...]
    file_names: tuple[str, ...]
    count: int


@dataclass(frozen=True)
class BufferedSceneExecutionResult:
    scene_id: str
    scene_trace_id: str
    events: tuple[dict[str, str], ...]
    qa_result: dict[str, Any]
    retries_used: int
    word_count: int
    continuity_tokens: tuple[str, ...]
    text: str
    image_url: str
    audio_url: str


class GeminiStoryAgent:
    def __init__(self) -> None:
        self.client = get_gemini_client()

    @staticmethod
    def _load_schema_text(filename: str) -> str:
        return (SCHEMAS_DIR / filename).read_text(encoding="utf-8")

    _source_manifest_for_extraction = staticmethod(source_manifest_for_extraction)
    _source_manifest_summary = staticmethod(source_manifest_summary)
    _is_youtube_video_asset = staticmethod(is_youtube_video_asset)
    _transcript_only_video_mode = staticmethod(transcript_only_video_mode)
    _should_upload_source_assets_for_extraction = staticmethod(should_upload_source_assets_for_extraction)
    _build_signal_extraction_prompt = staticmethod(build_signal_extraction_prompt)
    _transcript_needs_normalization = staticmethod(transcript_needs_normalization)
    _build_transcript_normalization_prompt = staticmethod(build_transcript_normalization_prompt)
    _build_quick_stream_planning_prompt = staticmethod(build_quick_stream_planning_prompt)
    _normalize_quick_stream_scenes = staticmethod(normalize_quick_stream_scenes)
    _normalize_quick_scene_identity = staticmethod(normalize_quick_scene_identity)
    _build_quick_scene_start_payload = staticmethod(build_quick_scene_start_payload)
    _quick_grounded_claim_cards = staticmethod(quick_grounded_claim_cards)

    async def _normalize_transcript_source_text(
        self,
        *,
        source_text: str,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> tuple[str, str]:
        return await normalize_transcript_source_text(
            client=self.client,
            source_text=source_text,
            source_manifest=source_manifest,
            source_manifest_summary=self._source_manifest_summary,
            build_transcript_normalization_prompt=self._build_transcript_normalization_prompt,
            parse_json_object_response=self._parse_json_object_response,
            signal_source_text_model=self._signal_source_text_model,
            transcript_only_video_mode=self._transcript_only_video_mode,
        )

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

    _should_use_text_backed_fast_extraction = staticmethod(should_use_text_backed_fast_extraction)

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

        modal_allowlist = allowed_modalities or {"audio", "image", "pdf_page"}
        upload_semaphore = asyncio.Semaphore(3)

        async def upload_asset(
            index: int,
            asset: SourceAssetSchema,
        ) -> tuple[int, Any | None, str | None]:
            if asset.modality not in modal_allowlist:
                return index, None, None

            local_path = asset_path_from_reference(asset.uri)
            if local_path is None:
                return index, None, None

            try:
                async with upload_semaphore:
                    uploaded = await self.client.aio.files.upload(
                        file=str(local_path),
                        config=types.UploadFileConfig(
                            display_name=asset.title or local_path.name,
                            mime_type=asset.mime_type,
                        ),
                    )
            except Exception as exc:
                print(f"Source upload failed for {asset.asset_id}: {exc}")
                return index, None, None

            upload_name = getattr(uploaded, "name", None)
            upload_uri = getattr(uploaded, "uri", None)
            upload_mime = getattr(uploaded, "mime_type", None) or asset.mime_type
            if not isinstance(upload_uri, str) or not upload_uri:
                return index, None, None

            part = types.Part.from_uri(
                file_uri=upload_uri,
                mime_type=upload_mime or "application/octet-stream",
            )
            return index, part, upload_name if isinstance(upload_name, str) and upload_name else None

        upload_results = await asyncio.gather(
            *(upload_asset(index, asset) for index, asset in enumerate(manifest.assets[:6])),
        )

        parts: list[Any] = []
        uploaded_file_names: list[str] = []
        for _, part, upload_name in sorted(upload_results, key=lambda item: item[0]):
            if upload_name:
                uploaded_file_names.append(upload_name)
            if part is not None:
                parts.append(part)

        return UploadedSourceAssets(
            parts=tuple(parts),
            file_names=tuple(uploaded_file_names),
            count=len(parts),
        )

    @staticmethod
    async def _save_image_and_get_url_async(
        *,
        request: Request,
        scene_id: str,
        image_bytes: bytes,
        prefix: str,
    ) -> str:
        return await asyncio.to_thread(
            save_image_and_get_url,
            request=request,
            scene_id=scene_id,
            image_bytes=image_bytes,
            prefix=prefix,
        )

    @staticmethod
    async def _compose_thumbnail_cover_and_get_url_async(
        *,
        request: Request,
        scene_id: str,
        source_url: str,
        title: str,
        support_text: str,
        cue_lines: list[str],
        prefix: str,
    ) -> str:
        return await asyncio.to_thread(
            compose_thumbnail_cover_and_get_url,
            request=request,
            scene_id=scene_id,
            source_url=source_url,
            title=title,
            support_text=support_text,
            cue_lines=cue_lines,
            prefix=prefix,
        )

    @staticmethod
    async def _generate_audio_and_get_url_async(
        *,
        request: Request,
        scene_id: str,
        text: str,
        prefix: str,
        playback_rate: float = 1.0,
    ) -> str:
        return await asyncio.to_thread(
            generate_audio_and_get_url,
            request=request,
            scene_id=scene_id,
            text=text,
            prefix=prefix,
            playback_rate=playback_rate,
        )

    @staticmethod
    async def _build_quick_video_async(
        *,
        request: Request,
        artifact: QuickArtifactSchema,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ):
        return await asyncio.to_thread(
            build_quick_video,
            request=request,
            artifact=artifact,
            source_manifest=source_manifest,
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
        return await build_signal_extraction_contents(
            document_text=document_text,
            source_manifest=source_manifest,
            schema_text=schema_text,
            version=version,
            uploaded_assets=uploaded_assets,
            source_manifest_summary=self._source_manifest_summary,
            build_signal_extraction_prompt=self._build_signal_extraction_prompt,
            transcript_only_video_mode=self._transcript_only_video_mode,
            build_asset_augmented_contents=self._build_asset_augmented_contents,
        )

    _build_source_text_recovery_prompt = staticmethod(build_source_text_recovery_prompt)
    _build_structural_signal_prompt = staticmethod(build_structural_signal_prompt)
    _build_creative_signal_prompt = staticmethod(build_creative_signal_prompt)
    _build_fallback_narrative_beats = staticmethod(build_fallback_narrative_beats)
    _build_fallback_visual_candidates = staticmethod(build_fallback_visual_candidates)
    _merge_signal_extraction_passes = staticmethod(merge_signal_extraction_passes)

    async def _recover_normalized_source_text(
        self,
        *,
        input_text: str,
        normalized_source_text: str,
        source_text_origin: str | None,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        uploaded_assets: UploadedSourceAssets | None = None,
    ) -> tuple[str, str | None]:
        return await recover_normalized_source_text(
            client=self.client,
            input_text=input_text,
            normalized_source_text=normalized_source_text,
            source_text_origin=source_text_origin,
            source_manifest=source_manifest,
            uploaded_assets=uploaded_assets,
            source_manifest_summary=self._source_manifest_summary,
            build_source_text_recovery_prompt=self._build_source_text_recovery_prompt,
            build_asset_augmented_contents=self._build_asset_augmented_contents,
            parse_json_object_response=self._parse_json_object_response,
            signal_source_text_model=self._signal_source_text_model,
        )

    async def _extract_signal_structural(
        self,
        *,
        normalized_source_text: str,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        uploaded_assets: UploadedSourceAssets | None = None,
    ) -> dict[str, Any]:
        return await extract_signal_structural(
            client=self.client,
            normalized_source_text=normalized_source_text,
            source_manifest=source_manifest,
            uploaded_assets=uploaded_assets,
            source_manifest_summary=self._source_manifest_summary,
            build_structural_signal_prompt=self._build_structural_signal_prompt,
            transcript_only_video_mode=self._transcript_only_video_mode,
            build_asset_augmented_contents=self._build_asset_augmented_contents,
            signal_structural_model=self._signal_structural_model,
            parse_json_object_response=self._parse_json_object_response,
        )

    async def _extract_signal_creative(
        self,
        *,
        normalized_source_text: str,
        structural_signal: dict[str, Any],
        source_manifest: SourceManifestSchema | dict[str, Any] | None = None,
        fallback_to_pro: bool = True,
    ) -> dict[str, Any]:
        return await extract_signal_creative(
            client=self.client,
            normalized_source_text=normalized_source_text,
            structural_signal=structural_signal,
            source_manifest=source_manifest,
            fallback_to_pro=fallback_to_pro,
            build_creative_signal_prompt=self._build_creative_signal_prompt,
            transcript_only_video_mode=self._transcript_only_video_mode,
            signal_creative_model=self._signal_creative_model,
            signal_structural_model=self._signal_structural_model,
            parse_json_object_response=self._parse_json_object_response,
        )

    _style_guide_for_mode = staticmethod(style_guide_for_mode)

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

    _source_asset_lookup = staticmethod(source_asset_lookup)
    _asset_duration_ms = staticmethod(asset_duration_ms)
    _coerce_timecode_ms = staticmethod(coerce_timecode_ms)
    _coerce_evidence_time_range_ms = staticmethod(coerce_evidence_time_range_ms)
    _structured_evidence_refs = staticmethod(structured_evidence_refs)
    _evidence_summary_bits = staticmethod(evidence_summary_bits)
    _media_ref_for_evidence = staticmethod(media_ref_for_evidence)
    _effective_evidence_media_modality = staticmethod(effective_evidence_media_modality)
    _evidence_page_index = staticmethod(evidence_page_index)
    _evidence_page_key = staticmethod(evidence_page_key)
    _media_page_key = staticmethod(media_page_key)
    _source_media_merge_key = staticmethod(source_media_merge_key)
    _richer_optional_text = staticmethod(richer_optional_text)
    _merge_source_media_item = staticmethod(merge_source_media_item)
    _merge_source_media_list = staticmethod(merge_source_media_list)
    _evidence_text_blob = staticmethod(evidence_text_blob)
    _is_frontmatter_pdf_evidence = staticmethod(is_frontmatter_pdf_evidence)
    _scene_is_opener_or_hook = staticmethod(scene_is_opener_or_hook)
    _is_frontmatter_pdf_media = staticmethod(is_frontmatter_pdf_media)
    _claim_has_non_frontmatter_media = staticmethod(claim_has_non_frontmatter_media)
    _should_exclude_frontmatter_evidence = staticmethod(should_exclude_frontmatter_evidence)
    _should_exclude_frontmatter_media = staticmethod(should_exclude_frontmatter_media)
    _sort_claim_evidence_for_scene = staticmethod(sort_claim_evidence_for_scene)
    _enrich_script_pack_with_source_media = staticmethod(enrich_script_pack_with_source_media)
    _build_source_media_warning_payload = staticmethod(build_source_media_warning_payload)

    @staticmethod
    def _resolve_source_media_payloads(
        *,
        request: Request,
        scene_id: str,
        source_media: list[SourceMediaRefSchema],
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return resolve_source_media_payloads(
            request=request,
            scene_id=scene_id,
            source_media=source_media,
            source_manifest=source_manifest,
            proof_locator_resolver=resolve_pdf_proof_locator,
        )

    _resolve_planner_artifact_type = staticmethod(resolve_planner_artifact_type)
    _resolve_artifact_policy = staticmethod(resolve_artifact_policy)
    _planner_source_text = staticmethod(planner_source_text)
    _salience_candidates = staticmethod(salience_candidates)
    _build_salience_prompt = staticmethod(build_salience_prompt)
    _build_forward_pull_prompt = staticmethod(build_forward_pull_prompt)
    _best_effort_salience_summary = staticmethod(best_effort_salience_summary)
    _forward_pull_guidance = staticmethod(forward_pull_guidance)
    _build_enrichment_context = staticmethod(build_enrichment_context)
    _validate_script_pack_against_enrichments = staticmethod(validate_script_pack_against_enrichments)
    _repair_script_pack_from_enrichments = staticmethod(repair_script_pack_from_enrichments)
    _build_replan_directives = staticmethod(build_replan_directives)
    _build_planner_qa_summary = staticmethod(build_planner_qa_summary)
    _build_render_profile_scene_context = staticmethod(build_render_profile_scene_context)
    _build_claim_grounding_maps = staticmethod(build_claim_grounding_maps)
    _build_scene_grounding_snippets = staticmethod(build_scene_grounding_snippets)
    _build_stream_scene_prompt = staticmethod(build_stream_scene_prompt)
    _continuity_hints_from_scene_context = staticmethod(continuity_hints_from_scene_context)
    _workflow_scene_override_constraints = staticmethod(workflow_scene_override_constraints)
    _build_regenerate_scene_prompt = staticmethod(build_regenerate_scene_prompt)
    _build_advanced_scene_queue_payloads = staticmethod(build_advanced_scene_queue_payloads)
    _prepare_advanced_scene_spec = staticmethod(prepare_advanced_scene_spec)
    _build_scene_start_payload = staticmethod(build_scene_start_payload)
    _default_scene_qa_result = staticmethod(default_scene_qa_result)
    _build_scene_attempt_constraints = staticmethod(build_scene_attempt_constraints)
    _active_scene_continuity = staticmethod(active_scene_continuity)
    _update_scene_continuity_memory = staticmethod(update_scene_continuity_memory)

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

    _derive_scene_count = staticmethod(derive_scene_count)
    _fallback_scene_plan = staticmethod(fallback_scene_plan)
    _build_script_pack_prompt = staticmethod(build_script_pack_prompt)
    _outline_to_script_pack = staticmethod(outline_to_script_pack)

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
            model=self._signal_structural_model(),
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
                model=self._signal_structural_model(),
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
        scene_prompt = self._build_stream_scene_prompt(
            topic=topic,
            audience=audience,
            tone=tone,
            scene_title=scene_title,
            narration_focus=narration_focus,
            style_guide=style_guide,
            visual_prompt=visual_prompt,
            scene_goal=scene_goal,
            artifact_type=artifact_type,
            scene_mode=scene_mode,
            layout_template=layout_template,
            focal_subject=focal_subject,
            visual_hierarchy=visual_hierarchy,
            modules=modules,
            claim_refs=claim_refs,
            claim_text_snippets=claim_text_snippets,
            evidence_text_snippets=evidence_text_snippets,
            crop_safe_regions=crop_safe_regions,
            continuity_hints=continuity_hints,
            extra_constraints=extra_constraints,
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
                        latest_image_url = await self._save_image_and_get_url_async(
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
                composited_image_url = await self._compose_thumbnail_cover_and_get_url_async(
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
            audio_url = await self._generate_audio_and_get_url_async(
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
        extra_constraints: list[str] | None = None,
    ) -> BufferedSceneExecutionResult:
        events: list[dict[str, str]] = []
        scene_id = scene.scene_id
        scene_trace_id = str(scene_trace_payload.get("scene_trace_id", ""))
        resolved_source_media_payloads = self._resolve_source_media_payloads(
            request=request,
            scene_id=scene_id,
            source_media=scene.source_media,
            source_manifest=source_manifest,
        )

        events.append(
            build_sse_event(
                "scene_start",
                {
                    "scene_id": scene_id,
                    "title": scene.title,
                    "claim_refs": [claim_ref for claim_ref in scene.claim_refs if claim_ref],
                    "evidence_refs": [evidence_ref for evidence_ref in scene.evidence_refs if evidence_ref],
                    "render_strategy": scene.render_strategy,
                    "source_media": resolved_source_media_payloads,
                    "trace": scene_trace_payload,
                },
            )
        )

        for source_media_payload in resolved_source_media_payloads:
            source_media_payload["trace"] = scene_trace_payload
            events.append(build_sse_event("source_media_ready", source_media_payload))
        if scene.source_media and not resolved_source_media_payloads:
            warning_payload = self._build_source_media_warning_payload(
                scene_id=scene_id,
                source_media=scene.source_media,
            )
            if warning_payload is not None:
                warning_payload["trace"] = scene_trace_payload
                print(
                    "[source_media_warning]",
                    {
                        "scene_id": scene_id,
                        "asset_ids": warning_payload["asset_ids"],
                        "expected_count": warning_payload["expected_count"],
                    },
                )
                events.append(build_sse_event("source_media_warning", warning_payload))

        retries_used = 0
        qa_result: dict[str, Any] = {
            **self._default_scene_qa_result(scene_id),
        }
        scene_result: dict[str, Any] = {}
        retry_constraints = list(retry_reason_constraints or [])
        override_constraints = list(extra_constraints or [])

        for attempt_index in range(2):
            scene_result = {}
            attempt_constraints = self._build_scene_attempt_constraints(
                acceptance_checks=list(scene.acceptance_checks),
                override_constraints=override_constraints,
                retry_constraints=retry_constraints,
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
            text=str(scene_result.get("text", "")),
            image_url=str(scene_result.get("image_url", "")),
            audio_url=str(scene_result.get("audio_url", "")),
        )

    async def _extract_signal_one_pass(
        self,
        *,
        input_text: str,
        source_manifest: SourceManifestSchema | dict[str, Any] | None,
        prompt_version: str,
        uploaded_assets: UploadedSourceAssets | None = None,
    ) -> dict[str, Any]:
        return await extract_signal_one_pass(
            client=self.client,
            input_text=input_text,
            source_manifest=source_manifest,
            prompt_version=prompt_version,
            uploaded_assets=uploaded_assets,
            load_schema_text=self._load_schema_text,
            build_signal_extraction_contents=self._build_signal_extraction_contents,
            signal_structural_model=self._signal_structural_model,
            parse_json_object_response=self._parse_json_object_response,
        )

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
            manifest_text_preview, _ = best_effort_manifest_text(source_manifest)
            if source_asset_count and self._should_upload_source_assets_for_extraction(
                source_manifest,
                has_embedded_manifest_text=bool(manifest_text_preview.strip()),
            ):
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

                if not normalized_source_text.strip():
                    raise ValueError("Unable to recover normalized source text from the uploaded source.")

                if self._should_use_text_backed_fast_extraction(
                    normalized_source_text=normalized_source_text,
                    uploaded_asset_count=uploaded_asset_count,
                ):
                    fast_started_at = time.perf_counter()
                    signal_data = await self._extract_signal_one_pass(
                        input_text=normalized_source_text,
                        source_manifest=source_manifest,
                        prompt_version=prompt_version,
                        uploaded_assets=uploaded_assets,
                    )
                    phase_timings_ms["single_pass_fast"] = int((time.perf_counter() - fast_started_at) * 1000)
                    extraction_mode = "single_pass_text_backed"
                else:
                    try:
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
            source_media = GeminiStoryAgent._merge_source_media_list(list(block.source_media))
            media_index_by_key = {
                GeminiStoryAgent._source_media_merge_key(item): index
                for index, item in enumerate(source_media)
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
                        asset=asset_lookup.get(evidence.asset_id),
                    )
                    if media_ref is None or evidence.asset_id not in asset_lookup:
                        continue

                    media_key = GeminiStoryAgent._source_media_merge_key(media_ref)
                    existing_index = media_index_by_key.get(media_key)
                    if existing_index is None:
                        source_media.append(media_ref)
                        media_index_by_key[media_key] = len(source_media) - 1
                    else:
                        source_media[existing_index] = GeminiStoryAgent._merge_source_media_item(
                            source_media[existing_index],
                            media_ref,
                        )
                    if GeminiStoryAgent._is_frontmatter_pdf_evidence(
                        evidence,
                        asset_lookup.get(evidence.asset_id),
                    ):
                        block_uses_frontmatter = True
                    break

                if len(source_media) >= 2:
                    break

            block.evidence_refs = evidence_refs[:6]
            block.source_media = GeminiStoryAgent._merge_source_media_list(source_media)[:2]
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
        return await self._save_image_and_get_url_async(
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
        return await self._save_image_and_get_url_async(
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

    async def generate_quick_video(self, payload: QuickVideoRequest, *, request: Request) -> dict[str, Any]:
        artifact = QuickArtifactSchema.model_validate(payload.artifact)
        if not artifact.blocks:
            return {"status": "error", "message": "Provide a quick artifact before generating a video."}

        content_signal = payload.content_signal if isinstance(payload.content_signal, dict) else {}
        working_artifact = artifact
        if working_artifact.reel is None or not working_artifact.reel.segments:
            reel = self._build_quick_reel_from_artifact(
                artifact=working_artifact,
                content_signal=content_signal,
                source_manifest=payload.source_manifest,
            )
            working_artifact = working_artifact.model_copy(update={"reel": reel})

        try:
            video = await self._build_quick_video_async(
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
        planning_prompt = self._build_quick_stream_planning_prompt(
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
            plan_response = await self.client.aio.models.generate_content(
                model=self._signal_structural_model(),
                contents=planning_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=OutlineSchema,
                ),
            )
            parsed_outline = OutlineSchema.model_validate_json(plan_response.text)
            planned_scene_count = len(parsed_outline.scenes[:4])
            scenes = self._normalize_quick_stream_scenes(
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
                    self._normalize_quick_scene_identity(scene=scene, index=idx)
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
                    self._build_quick_scene_start_payload(
                        scene_id=scene_id,
                        title=title,
                        claim_refs=claim_refs,
                        scene_trace_payload=scene_trace_payload,
                    ),
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

        render_context = self._build_render_profile_scene_context(render_profile)
        visual_mode = render_context.visual_mode
        must_include = list(render_context.must_include)
        must_avoid = list(render_context.must_avoid)
        goal = render_context.goal
        style_guide = render_context.style_guide

        cp3 = add_checkpoint(
            trace,
            checkpoint="CP3_RENDER_LOCKED",
            status="passed",
            details={"visual_mode": visual_mode, "goal": str(render_profile.get("goal", "teach"))},
        )
        yield build_checkpoint_event(trace, cp3)

        thesis = content_signal.get("thesis", {}).get("one_liner", "A generic topic")
        claim_ids, claim_text_lookup, claim_evidence_lookup = self._build_claim_grounding_maps(
            content_signal
        )
        audience_descriptor = render_context.audience_descriptor

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
                    "scenes": self._build_advanced_scene_queue_payloads(script_pack),
                    "optimized_count": script_pack.scene_count,
                    "trace": trace_meta(trace, checkpoint="CP4_SCRIPT_LOCKED"),
                },
            )

            continuity_memory: list[str] = []
            scene_claim_map: dict[str, list[str]] = {}
            prepared_scenes = []

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
                claim_text_snippets, evidence_text_snippets = self._build_scene_grounding_snippets(
                    claim_refs=claim_refs,
                    claim_text_lookup=claim_text_lookup,
                    claim_evidence_lookup=claim_evidence_lookup,
                )
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
                    self._prepare_advanced_scene_spec(
                        scene=scene,
                        scene_id=scene_id,
                        title=title,
                        scene_trace_id=scene_trace_id,
                        scene_trace_payload=scene_trace_payload,
                        claim_refs=claim_refs,
                        evidence_refs=evidence_refs,
                        claim_text_snippets=claim_text_snippets,
                        evidence_text_snippets=evidence_text_snippets,
                    )
                )

            if prepared_scenes:
                first_spec = prepared_scenes[0]
                first_scene = first_spec.scene
                first_scene_id = first_spec.scene_id
                first_scene_trace_id = first_spec.scene_trace_id
                first_scene_trace_payload = dict(first_spec.scene_trace_payload)
                first_title = first_spec.title
                first_scene_source_media_payloads = self._resolve_source_media_payloads(
                    request=request,
                    scene_id=first_scene_id,
                    source_media=first_scene.source_media,
                    source_manifest=payload.source_manifest,
                )

                yield build_sse_event(
                    "scene_start",
                    self._build_scene_start_payload(
                        spec=first_spec,
                        source_media=first_scene_source_media_payloads,
                    ),
                )

                for source_media_payload in first_scene_source_media_payloads:
                    source_media_payload["trace"] = first_scene_trace_payload
                    yield build_sse_event("source_media_ready", source_media_payload)
                if first_scene.source_media and not first_scene_source_media_payloads:
                    warning_payload = self._build_source_media_warning_payload(
                        scene_id=first_scene_id,
                        source_media=first_scene.source_media,
                    )
                    if warning_payload is not None:
                        warning_payload["trace"] = first_scene_trace_payload
                        print(
                            "[source_media_warning]",
                            {
                                "scene_id": first_scene_id,
                                "asset_ids": warning_payload["asset_ids"],
                                "expected_count": warning_payload["expected_count"],
                            },
                        )
                        yield build_sse_event("source_media_warning", warning_payload)

                first_retries_used = 0
                first_qa_result: dict[str, Any] = self._default_scene_qa_result(first_scene_id)
                first_scene_result: dict[str, Any] = {}
                first_retry_reason_constraints: list[str] = []

                for attempt_index in range(2):
                    first_scene_result = {}
                    active_continuity = self._active_scene_continuity(
                        continuity_memory,
                        list(first_scene.continuity_refs),
                    )
                    attempt_constraints = self._build_scene_attempt_constraints(
                        acceptance_checks=list(first_scene.acceptance_checks),
                        retry_constraints=first_retry_reason_constraints,
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
                        claim_text_snippets=list(first_spec.claim_text_snippets),
                        evidence_text_snippets=list(first_spec.evidence_text_snippets),
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
                continuity_memory = self._update_scene_continuity_memory(
                    continuity_memory,
                    title=first_title,
                    continuity_tokens=first_continuity_tokens,
                )
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
                            scene=spec.scene,
                            thesis=thesis,
                            audience_descriptor=audience_descriptor,
                            goal=goal,
                            style_guide=style_guide,
                            script_pack=script_pack,
                            source_manifest=payload.source_manifest,
                            must_include=must_include,
                            must_avoid=must_avoid,
                            claim_text_snippets=list(spec.claim_text_snippets),
                            evidence_text_snippets=list(spec.evidence_text_snippets),
                            active_continuity=self._active_scene_continuity(
                                continuity_snapshot,
                                list(spec.scene.continuity_refs),
                            ),
                            scene_trace_payload=dict(spec.scene_trace_payload),
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

                    continuity_memory = self._update_scene_continuity_memory(
                        continuity_memory,
                        title=spec.title,
                        continuity_tokens=buffered_result.continuity_tokens,
                    )

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

    async def regenerate_workflow_scene(
        self,
        *,
        request: Request,
        workflow_payload: AdvancedStreamRequest,
        payload: WorkflowSceneRegenerateRequest,
    ) -> dict[str, Any]:
        instruction = re.sub(r"\s+", " ", payload.instruction or "").strip()
        if not instruction:
            return {"status": "error", "message": "Provide an instruction for the scene override."}

        content_signal = workflow_payload.content_signal
        render_profile = workflow_payload.render_profile
        artifact_scope = self._resolve_artifact_scope(
            requested_scope=workflow_payload.artifact_scope,
            render_profile=render_profile,
            default_scope=["story_cards", "voiceover", "social_caption"],
        )
        run_id = self._new_run_id("workflow-scene-regen-run")
        trace = init_trace_envelope(
            trace_id=f"trace-{uuid4().hex[:12]}",
            run_id=run_id,
            flow="workflow_scene_regeneration",
            artifact_scope=artifact_scope,
        )
        scene_id = payload.scene_id

        try:
            approved_script_pack_raw = workflow_payload.script_pack
            if not isinstance(approved_script_pack_raw, dict):
                raise ValueError("Generate and lock the script pack before regenerating a scene.")

            script_pack = ScriptPack.model_validate(approved_script_pack_raw)
            has_signal = bool(
                content_signal.get("thesis")
                or content_signal.get("key_claims")
                or content_signal.get("narrative_beats")
            )
            add_checkpoint(
                trace,
                checkpoint="CP1_SIGNAL_READY",
                status="passed" if has_signal else "failed",
                details={"source": "workflow_payload", "has_signal": has_signal},
            )
            if not has_signal:
                raise ValueError("Signal is missing. Run extraction before regenerating a scene.")

            add_checkpoint(
                trace,
                checkpoint="CP2_ARTIFACTS_LOCKED",
                status="passed",
                details={"artifact_scope": artifact_scope},
            )

            render_context = self._build_render_profile_scene_context(render_profile)
            visual_mode = render_context.visual_mode
            must_include = list(render_context.must_include)
            must_avoid = list(render_context.must_avoid)
            goal = render_context.goal
            style_guide = render_context.style_guide

            add_checkpoint(
                trace,
                checkpoint="CP3_RENDER_LOCKED",
                status="passed",
                details={"visual_mode": visual_mode, "goal": str(render_profile.get("goal", "teach"))},
            )

            thesis = content_signal.get("thesis", {}).get("one_liner", "A generic topic")
            _, claim_text_lookup, claim_evidence_lookup = self._build_claim_grounding_maps(
                content_signal
            )
            audience_descriptor = render_context.audience_descriptor

            script_pack, _, _ = self._enrich_script_pack_with_source_media(
                script_pack=script_pack,
                content_signal=content_signal,
                source_manifest=workflow_payload.source_manifest,
            )

            add_checkpoint(
                trace,
                checkpoint="CP4_SCRIPT_LOCKED",
                status="passed",
                details={
                    "scene_count": script_pack.scene_count,
                    "source": "workflow_locked_script_pack",
                },
            )

            target_scene = next((scene for scene in script_pack.scenes if scene.scene_id == scene_id), None)
            if target_scene is None:
                raise ValueError(f"Scene {scene_id} is not available in the locked script pack.")

            claim_refs = [claim_ref for claim_ref in target_scene.claim_refs if claim_ref]
            evidence_refs = [evidence_ref for evidence_ref in target_scene.evidence_refs if evidence_ref]
            claim_text_snippets, evidence_text_snippets = self._build_scene_grounding_snippets(
                claim_refs=claim_refs,
                claim_text_lookup=claim_text_lookup,
                claim_evidence_lookup=claim_evidence_lookup,
            )

            scene_trace_id = f"{trace.trace_id}-{scene_id}-{uuid4().hex[:8]}"
            add_or_update_scene_trace(
                trace,
                scene_id=scene_id,
                scene_trace_id=scene_trace_id,
                claim_refs=claim_refs,
                evidence_refs=evidence_refs,
                render_strategy=target_scene.render_strategy,
                media_asset_ids=[item.asset_id for item in target_scene.source_media if item.asset_id],
            )
            scene_trace_payload = trace_meta(trace, scene_trace_id=scene_trace_id)
            active_continuity = (
                self._continuity_hints_from_scene_context(payload.prior_scene_context)
                + list(target_scene.continuity_refs)
            )[-6:]

            buffered_result = await self._execute_buffered_advanced_scene(
                request=request,
                scene=target_scene,
                thesis=thesis,
                audience_descriptor=audience_descriptor,
                goal=goal,
                style_guide=style_guide,
                script_pack=script_pack,
                source_manifest=workflow_payload.source_manifest,
                must_include=must_include,
                must_avoid=must_avoid,
                claim_text_snippets=claim_text_snippets,
                evidence_text_snippets=evidence_text_snippets,
                active_continuity=active_continuity,
                scene_trace_payload=scene_trace_payload,
                extra_constraints=self._workflow_scene_override_constraints(
                    instruction,
                    payload.current_text,
                ),
            )

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
            add_checkpoint(
                trace,
                checkpoint="CP5_STREAM_COMPLETE",
                status="passed",
                details={
                    "mode": "workflow_scene_override",
                    "scene_id": scene_id,
                    "qa_status": str(buffered_result.qa_result.get("status", "")),
                },
            )

            return {
                "status": "success",
                "scene_id": scene_id,
                "text": buffered_result.text,
                "imageUrl": buffered_result.image_url,
                "audioUrl": buffered_result.audio_url,
                "qa_status": buffered_result.qa_result.get("status"),
                "qa_reasons": buffered_result.qa_result.get("reasons", []),
                "qa_score": buffered_result.qa_result.get("score"),
                "qa_word_count": buffered_result.qa_result.get("word_count"),
                "auto_retries": buffered_result.retries_used,
                "trace": trace.model_dump(),
            }
        except Exception as exc:
            print(f"Workflow scene regeneration error: {exc}")
            add_checkpoint(
                trace,
                checkpoint="CP5_STREAM_COMPLETE",
                status="failed",
                details={
                    "mode": "workflow_scene_override",
                    "scene_id": scene_id,
                    "error": str(exc),
                },
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
            regen_prompt = self._build_regenerate_scene_prompt(
                scene_id=scene_id,
                instruction=instruction,
                current_text=current_text,
                style_guide=style_guide,
            )

            response = await self.client.aio.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=regen_prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )
            updated_text, image_bytes = extract_parts_from_response(response)

            image_url = ""
            if image_bytes:
                image_url = await self._save_image_and_get_url_async(
                    request=request,
                    scene_id=scene_id,
                    image_bytes=image_bytes,
                    prefix="regen",
                )

            audio_url = await self._generate_audio_and_get_url_async(
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
