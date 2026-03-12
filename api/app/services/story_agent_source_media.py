from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from fastapi import Request

from app.schemas.requests import (
    EvidenceRefSchema,
    ScriptPack,
    ScriptPackScene,
    SourceAssetSchema,
    SourceManifestSchema,
    SourceMediaRefSchema,
)
from app.services.image_pipeline import (
    asset_path_from_reference,
    crop_source_region_and_get_url,
    public_asset_url,
)
from app.services.source_ingest import resolve_pdf_proof_locator


def source_manifest_for_extraction(
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


def source_manifest_summary(source_manifest: SourceManifestSchema | dict[str, Any] | None) -> str:
    manifest = source_manifest_for_extraction(source_manifest)
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


def is_youtube_video_asset(asset: SourceAssetSchema) -> bool:
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


def transcript_only_video_mode(source_manifest: SourceManifestSchema | dict[str, Any] | None) -> bool:
    manifest = source_manifest_for_extraction(source_manifest)
    if manifest is None or not manifest.assets:
        return False
    return any(is_youtube_video_asset(asset) for asset in manifest.assets)


def should_upload_source_assets_for_extraction(
    source_manifest: SourceManifestSchema | dict[str, Any] | None,
    *,
    has_embedded_manifest_text: bool,
) -> bool:
    manifest = source_manifest_for_extraction(source_manifest)
    if manifest is None or not manifest.assets:
        return False

    uploadable_assets = [
        asset
        for asset in manifest.assets[:6]
        if asset.modality in {"audio", "image", "pdf_page", "video"}
        and asset_path_from_reference(asset.uri) is not None
    ]
    if not uploadable_assets:
        return False

    if has_embedded_manifest_text and all(asset.modality == "pdf_page" for asset in uploadable_assets):
        return False

    return True


def source_asset_lookup(
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


def asset_duration_ms(asset: SourceAssetSchema | None) -> int | None:
    if asset is None:
        return None
    if isinstance(asset.duration_ms, int) and asset.duration_ms >= 0:
        return asset.duration_ms
    if isinstance(asset.metadata, dict):
        raw_duration = asset.metadata.get("duration_ms")
        if isinstance(raw_duration, (int, float)) and raw_duration >= 0:
            return int(raw_duration)
    return None


def coerce_timecode_ms(raw_value: Any, *, asset_duration_ms: int | None = None) -> int | None:
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


def coerce_evidence_time_range_ms(
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

    start_ms = coerce_timecode_ms(raw_start, asset_duration_ms=asset_duration_ms)
    end_ms = coerce_timecode_ms(raw_end, asset_duration_ms=asset_duration_ms)
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


def structured_evidence_refs(
    content_signal: dict[str, Any],
    source_manifest: SourceManifestSchema | dict[str, Any] | None = None,
) -> tuple[dict[str, list[EvidenceRefSchema]], dict[str, EvidenceRefSchema], list[str]]:
    by_claim: dict[str, list[EvidenceRefSchema]] = {}
    by_id: dict[str, EvidenceRefSchema] = {}
    evidence_ids: list[str] = []
    asset_lookup = source_asset_lookup(source_manifest)

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
            modality = str(snippet.get("modality") or snippet.get("type") or "").strip().lower()
            asset_id = str(snippet.get("asset_id", "")).strip()
            if modality not in {"text", "audio", "video", "image", "pdf_page"} or not asset_id:
                continue

            evidence_id = str(snippet.get("evidence_id", "")).strip() or f"{claim_id}-e{index}"
            duration_ms = asset_duration_ms(asset_lookup.get(asset_id))
            start_ms, end_ms, timing_inferred = coerce_evidence_time_range_ms(
                snippet,
                modality=modality,
                asset_duration_ms=duration_ms,
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


def evidence_summary_bits(evidence_items: list[Any]) -> list[str]:
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


def media_ref_for_evidence(
    *,
    claim_ref: str,
    evidence: EvidenceRefSchema,
    asset: SourceAssetSchema | None = None,
) -> SourceMediaRefSchema | None:
    resolved_modality = evidence.modality
    if resolved_modality not in {"audio", "video", "image", "pdf_page"}:
        asset_modality = asset.modality if asset is not None else None
        if asset_modality not in {"audio", "video", "image", "pdf_page"}:
            return None
        resolved_modality = asset_modality

    if resolved_modality not in {"audio", "video", "image", "pdf_page"}:
        return None

    usage = "proof_clip" if resolved_modality in {"audio", "video"} else "region_crop" if evidence.bbox_norm else "callout"
    label = evidence.quote_text or evidence.visual_context or evidence.transcript_text or f"Proof for {claim_ref}"
    return SourceMediaRefSchema(
        asset_id=evidence.asset_id,
        modality=resolved_modality,  # type: ignore[arg-type]
        usage=usage,  # type: ignore[arg-type]
        claim_refs=[claim_ref],
        evidence_refs=[evidence.evidence_id],
        start_ms=evidence.start_ms,
        end_ms=evidence.end_ms,
        timing_inferred=evidence.timing_inferred,
        page_index=evidence.page_index if evidence.page_index is not None else (asset.page_index if asset is not None else None),
        bbox_norm=evidence.bbox_norm,
        label=label[:96],
        quote_text=evidence.quote_text,
        visual_context=evidence.visual_context,
        muted=resolved_modality != "audio",
        loop=resolved_modality == "audio",
    )


def effective_evidence_media_modality(
    evidence: EvidenceRefSchema,
    asset: SourceAssetSchema | None = None,
) -> str | None:
    if evidence.modality in {"audio", "video", "image", "pdf_page"}:
        return evidence.modality
    if asset is not None and asset.modality in {"audio", "video", "image", "pdf_page"}:
        return asset.modality
    return None


def evidence_page_index(
    evidence: EvidenceRefSchema,
    asset: SourceAssetSchema | None = None,
) -> int | None:
    if evidence.page_index is not None:
        return evidence.page_index
    if asset is not None:
        return asset.page_index
    return None


def evidence_page_key(
    evidence: EvidenceRefSchema,
    asset: SourceAssetSchema | None = None,
) -> tuple[str, int | None]:
    return (evidence.asset_id, evidence_page_index(evidence, asset))


def media_page_key(media: SourceMediaRefSchema) -> tuple[str, int | None]:
    return (media.asset_id, media.page_index)


def source_media_merge_key(
    media: SourceMediaRefSchema,
) -> tuple[str, str, str, int | None, int | None, int | None, tuple[float, ...]]:
    return (
        media.asset_id,
        media.modality,
        media.usage,
        media.start_ms,
        media.end_ms,
        media.page_index,
        tuple(float(value) for value in (media.bbox_norm or [])),
    )


def richer_optional_text(existing: str | None, incoming: str | None) -> str | None:
    existing_clean = str(existing or "").strip()
    incoming_clean = str(incoming or "").strip()
    if not existing_clean:
        return incoming_clean or None
    if not incoming_clean:
        return existing_clean
    return incoming_clean if len(incoming_clean) > len(existing_clean) else existing_clean


def merge_source_media_item(
    existing: SourceMediaRefSchema,
    incoming: SourceMediaRefSchema,
) -> SourceMediaRefSchema:
    existing_page_index = existing.page_index if isinstance(existing.page_index, int) and existing.page_index > 0 else None
    incoming_page_index = incoming.page_index if isinstance(incoming.page_index, int) and incoming.page_index > 0 else None
    return existing.model_copy(
        update={
            "claim_refs": list(dict.fromkeys([*existing.claim_refs, *incoming.claim_refs])),
            "evidence_refs": list(dict.fromkeys([*existing.evidence_refs, *incoming.evidence_refs])),
            "start_ms": existing.start_ms if existing.start_ms is not None else incoming.start_ms,
            "end_ms": existing.end_ms if existing.end_ms is not None else incoming.end_ms,
            "timing_inferred": existing.timing_inferred or incoming.timing_inferred,
            "page_index": existing_page_index if existing_page_index is not None else incoming_page_index,
            "bbox_norm": existing.bbox_norm or incoming.bbox_norm,
            "loop": existing.loop or incoming.loop,
            "muted": existing.muted and incoming.muted,
            "label": richer_optional_text(existing.label, incoming.label),
            "quote_text": richer_optional_text(existing.quote_text, incoming.quote_text),
            "visual_context": richer_optional_text(existing.visual_context, incoming.visual_context),
        }
    )


def merge_source_media_list(source_media: list[SourceMediaRefSchema]) -> list[SourceMediaRefSchema]:
    merged: list[SourceMediaRefSchema] = []
    for item in source_media:
        media_key = source_media_merge_key(item)
        existing_index = next(
            (
                index
                for index, existing in enumerate(merged)
                if source_media_merge_key(existing) == media_key
            ),
            None,
        )
        if existing_index is None:
            merged.append(item)
            continue
        merged[existing_index] = merge_source_media_item(merged[existing_index], item)
    return merged


def evidence_text_blob(evidence: EvidenceRefSchema) -> str:
    return " ".join(
        part.strip()
        for part in [
            evidence.quote_text or "",
            evidence.transcript_text or "",
            evidence.visual_context or "",
        ]
        if part and part.strip()
    ).lower()


def is_frontmatter_pdf_evidence(
    evidence: EvidenceRefSchema,
    asset: SourceAssetSchema | None = None,
) -> bool:
    if effective_evidence_media_modality(evidence, asset) != "pdf_page":
        return False
    page_index = evidence_page_index(evidence, asset)
    text_blob = evidence_text_blob(evidence)
    if "abstract" in text_blob or "executive summary" in text_blob:
        return True
    return page_index == 1


def scene_is_opener_or_hook(scene: ScriptPackScene, scene_index: int) -> bool:
    if scene_index == 0:
        return True
    scene_role = (scene.scene_role or "").strip().lower()
    return scene_role in {"hook", "bait", "bait_hook", "setup"}


def is_frontmatter_pdf_media(
    media: SourceMediaRefSchema,
    asset: SourceAssetSchema | None = None,
) -> bool:
    effective_modality = media.modality or (asset.modality if asset is not None else None)
    if effective_modality != "pdf_page":
        return False
    page_index = media.page_index if media.page_index is not None else (asset.page_index if asset is not None else None)
    text_blob = " ".join(
        part.strip()
        for part in [
            media.label or "",
            media.quote_text or "",
            media.visual_context or "",
        ]
        if part and part.strip()
    ).lower()
    if "abstract" in text_blob or "executive summary" in text_blob:
        return True
    return page_index == 1


def claim_has_non_frontmatter_media(
    claim_ref: str,
    evidence_items: list[EvidenceRefSchema],
    asset_lookup: dict[str, SourceAssetSchema],
) -> bool:
    return any(
        evidence.asset_id in asset_lookup
        and not is_frontmatter_pdf_evidence(evidence, asset_lookup.get(evidence.asset_id))
        for evidence in evidence_items
        if effective_evidence_media_modality(evidence, asset_lookup.get(evidence.asset_id))
        in {"audio", "image", "pdf_page", "video"}
    )


def should_exclude_frontmatter_evidence(
    *,
    evidence: EvidenceRefSchema,
    claim_refs: list[str],
    allow_frontmatter: bool,
    evidence_by_claim: dict[str, list[EvidenceRefSchema]],
    asset_lookup: dict[str, SourceAssetSchema],
) -> bool:
    if allow_frontmatter:
        return False
    asset = asset_lookup.get(evidence.asset_id)
    if not is_frontmatter_pdf_evidence(evidence, asset):
        return False
    return any(
        claim_has_non_frontmatter_media(claim_ref, evidence_by_claim.get(claim_ref, []), asset_lookup)
        for claim_ref in claim_refs
        if claim_ref
    )


def should_exclude_frontmatter_media(
    *,
    media: SourceMediaRefSchema,
    claim_refs: list[str],
    allow_frontmatter: bool,
    evidence_by_claim: dict[str, list[EvidenceRefSchema]],
    asset_lookup: dict[str, SourceAssetSchema],
) -> bool:
    if allow_frontmatter:
        return False
    asset = asset_lookup.get(media.asset_id)
    if not is_frontmatter_pdf_media(media, asset):
        return False
    return any(
        claim_has_non_frontmatter_media(claim_ref, evidence_by_claim.get(claim_ref, []), asset_lookup)
        for claim_ref in claim_refs
        if claim_ref
    )


def sort_claim_evidence_for_scene(
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

    claim_has_non_frontmatter = claim_has_non_frontmatter_media(claim_ref, evidence_items, asset_lookup)

    filtered_items = [
        evidence
        for evidence in evidence_items
        if allow_frontmatter
        or not is_frontmatter_pdf_evidence(evidence, asset_lookup.get(evidence.asset_id))
        or not claim_has_non_frontmatter
    ]
    candidates = filtered_items or evidence_items

    def score(evidence: EvidenceRefSchema) -> float:
        asset = asset_lookup.get(evidence.asset_id)
        effective_modality = effective_evidence_media_modality(evidence, asset)
        page_key = evidence_page_key(evidence, asset)
        page_index = evidence_page_index(evidence, asset)
        is_frontmatter = is_frontmatter_pdf_evidence(evidence, asset)
        score_value = float(evidence.confidence or 0.5) * 10.0

        if effective_modality == "audio":
            score_value += 16.0
        elif effective_modality == "image":
            score_value += 18.0
        elif effective_modality == "pdf_page":
            score_value += 14.0
        elif effective_modality == "video":
            score_value += 12.0
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
            -(evidence_page_index(evidence, asset_lookup.get(evidence.asset_id)) or 0),
        ),
        reverse=True,
    )


def enrich_script_pack_with_source_media(
    *,
    script_pack: ScriptPack,
    content_signal: dict[str, Any],
    source_manifest: SourceManifestSchema | dict[str, Any] | None,
) -> tuple[ScriptPack, dict[str, list[str]], list[str]]:
    asset_lookup = source_asset_lookup(source_manifest)
    evidence_by_claim, evidence_by_id, evidence_ids = structured_evidence_refs(content_signal, source_manifest)
    if not evidence_by_claim or not asset_lookup:
        return script_pack, {scene.scene_id: list(scene.evidence_refs) for scene in script_pack.scenes}, evidence_ids

    enriched = script_pack.model_copy(deep=True)
    scene_evidence_map: dict[str, list[str]] = {}
    page_usage_counts: dict[tuple[str, int | None], int] = {}
    evidence_usage_counts: dict[str, int] = {}
    abstract_scene_claimed = False
    evidence_claim_refs: dict[str, list[str]] = {}

    for claim_ref, evidence_items in evidence_by_claim.items():
        for evidence in evidence_items:
            if evidence.evidence_id:
                evidence_claim_refs.setdefault(evidence.evidence_id, [])
                if claim_ref not in evidence_claim_refs[evidence.evidence_id]:
                    evidence_claim_refs[evidence.evidence_id].append(claim_ref)

    for scene_index, scene in enumerate(enriched.scenes):
        allow_frontmatter = scene_is_opener_or_hook(scene, scene_index) and not abstract_scene_claimed
        scene_claim_refs = [claim_ref for claim_ref in scene.claim_refs if claim_ref]
        evidence_refs = [
            evidence_ref
            for evidence_ref in list(scene.evidence_refs)
            if not (
                (evidence := evidence_by_id.get(evidence_ref)) is not None
                and should_exclude_frontmatter_evidence(
                    evidence=evidence,
                    claim_refs=evidence_claim_refs.get(evidence_ref, scene_claim_refs) or scene_claim_refs,
                    allow_frontmatter=allow_frontmatter,
                    evidence_by_claim=evidence_by_claim,
                    asset_lookup=asset_lookup,
                )
            )
        ]
        source_media = [
            media
            for media in merge_source_media_list(list(scene.source_media))
            if not should_exclude_frontmatter_media(
                media=media,
                claim_refs=list(media.claim_refs) or scene_claim_refs,
                allow_frontmatter=allow_frontmatter,
                evidence_by_claim=evidence_by_claim,
                asset_lookup=asset_lookup,
            )
        ]
        media_index_by_key = {
            source_media_merge_key(item): index
            for index, item in enumerate(source_media)
        }
        scene_uses_frontmatter = False

        for claim_ref in scene_claim_refs[:4]:
            claim_page_like_selected = False
            claim_audio_selected = False
            ranked_evidence = sort_claim_evidence_for_scene(
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

                media_ref = media_ref_for_evidence(
                    claim_ref=claim_ref,
                    evidence=evidence,
                    asset=asset_lookup.get(evidence.asset_id),
                )
                if media_ref is None:
                    if evidence.evidence_id not in evidence_refs:
                        evidence_refs.append(evidence.evidence_id)
                    continue

                media_key = source_media_merge_key(media_ref)
                existing_index = media_index_by_key.get(media_key)
                if evidence.evidence_id not in evidence_refs:
                    evidence_refs.append(evidence.evidence_id)
                if existing_index is None:
                    source_media.append(media_ref)
                    media_index_by_key[media_key] = len(source_media) - 1
                else:
                    source_media[existing_index] = merge_source_media_item(source_media[existing_index], media_ref)
                if is_page_like:
                    claim_page_like_selected = True
                if evidence.modality == "audio":
                    claim_audio_selected = True
                if is_frontmatter_pdf_evidence(evidence, asset_lookup.get(evidence.asset_id)):
                    scene_uses_frontmatter = True
                if len(source_media) >= 3:
                    break
            if len(source_media) >= 3:
                break

        if len(source_media) < 3:
            fallback_claim_ref = next((claim for claim in scene_claim_refs if claim), "evidence")
            for evidence_ref in scene.evidence_refs[:6]:
                evidence = evidence_by_id.get(evidence_ref)
                if evidence is None or evidence.asset_id not in asset_lookup:
                    continue
                fallback_claim_refs = evidence_claim_refs.get(evidence_ref, scene_claim_refs) or scene_claim_refs
                if should_exclude_frontmatter_evidence(
                    evidence=evidence,
                    claim_refs=fallback_claim_refs,
                    allow_frontmatter=allow_frontmatter,
                    evidence_by_claim=evidence_by_claim,
                    asset_lookup=asset_lookup,
                ):
                    continue

                media_ref = media_ref_for_evidence(
                    claim_ref=fallback_claim_ref,
                    evidence=evidence,
                    asset=asset_lookup.get(evidence.asset_id),
                )
                if media_ref is None:
                    continue
                if should_exclude_frontmatter_media(
                    media=media_ref,
                    claim_refs=fallback_claim_refs,
                    allow_frontmatter=allow_frontmatter,
                    evidence_by_claim=evidence_by_claim,
                    asset_lookup=asset_lookup,
                ):
                    continue

                media_key = source_media_merge_key(media_ref)
                existing_index = media_index_by_key.get(media_key)
                if existing_index is None:
                    source_media.append(media_ref)
                    media_index_by_key[media_key] = len(source_media) - 1
                else:
                    source_media[existing_index] = merge_source_media_item(source_media[existing_index], media_ref)
                if len(source_media) >= 3:
                    break

        scene.evidence_refs = evidence_refs[:8]
        scene.source_media = merge_source_media_list(source_media)[:3]
        if scene.source_media and scene.render_strategy == "generated":
            scene.render_strategy = "hybrid"

        for module in scene.modules:
            module_evidence_refs = list(module.evidence_refs)
            module_source_media = merge_source_media_list(list(module.source_media))
            module_media_index_by_key = {
                source_media_merge_key(item): index
                for index, item in enumerate(module_source_media)
            }
            for claim_ref in module.claim_refs[:3]:
                for evidence in evidence_by_claim.get(claim_ref, [])[:2]:
                    if evidence.evidence_id not in module_evidence_refs:
                        module_evidence_refs.append(evidence.evidence_id)
                    media_ref = media_ref_for_evidence(
                        claim_ref=claim_ref,
                        evidence=evidence,
                        asset=asset_lookup.get(evidence.asset_id),
                    )
                    if media_ref is not None and evidence.asset_id in asset_lookup:
                        media_key = source_media_merge_key(media_ref)
                        existing_index = module_media_index_by_key.get(media_key)
                        if existing_index is None:
                            module_source_media.append(media_ref)
                            module_media_index_by_key[media_key] = len(module_source_media) - 1
                        else:
                            module_source_media[existing_index] = merge_source_media_item(
                                module_source_media[existing_index],
                                media_ref,
                            )
            module.evidence_refs = module_evidence_refs[:6]
            module.source_media = merge_source_media_list(module_source_media)[:2]

        for evidence_id in scene.evidence_refs:
            evidence_usage_counts[evidence_id] = evidence_usage_counts.get(evidence_id, 0) + 1
        for media in scene.source_media:
            page_key = media_page_key(media)
            page_usage_counts[page_key] = page_usage_counts.get(page_key, 0) + 1
        if scene_uses_frontmatter:
            abstract_scene_claimed = True
        scene_evidence_map[scene.scene_id] = list(scene.evidence_refs)

    return enriched, scene_evidence_map, evidence_ids


def resolve_source_media_payloads(
    *,
    request: Request,
    scene_id: str,
    source_media: list[SourceMediaRefSchema],
    source_manifest: SourceManifestSchema | dict[str, Any] | None,
    proof_locator_resolver: Any = resolve_pdf_proof_locator,
) -> list[dict[str, Any]]:
    asset_lookup = source_asset_lookup(source_manifest)
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
            proof_locator = proof_locator_resolver(
                asset_ref=asset.uri or original_url,
                page_index=payload["page_index"],
                quote_text=media.quote_text,
                transcript_text=None,
                visual_context=media.visual_context,
            )
            if proof_locator is not None:
                payload.update(proof_locator)

    return payloads


def build_source_media_warning_payload(
    *,
    scene_id: str,
    source_media: list[SourceMediaRefSchema],
) -> dict[str, Any] | None:
    if not source_media:
        return None

    asset_ids = sorted({media.asset_id for media in source_media if media.asset_id})
    expected_count = len(source_media)
    return {
        "scene_id": scene_id,
        "message": (
            "Source proof was planned for this scene, but no resolvable proof links were produced. "
            "Check the uploaded asset manifest and generated media URLs."
        ),
        "asset_ids": asset_ids,
        "expected_count": expected_count,
    }
