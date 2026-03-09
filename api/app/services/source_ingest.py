from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import mimetypes
import os
import re
from urllib.parse import urlparse
from difflib import SequenceMatcher
from uuid import uuid4

from fastapi import HTTPException, Request, UploadFile

from app.config import ASSET_DIR
from app.schemas.requests import SourceAssetSchema, SourceManifestSchema
from app.services.image_pipeline import base_url

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency at runtime
    PdfReader = None  # type: ignore[assignment]


_SUPPORTED_MODALITIES = {
    "image/": "image",
    "audio/": "audio",
    "video/": "video",
}

_SUPPORTED_EXACT_MIME_TYPES = {
    "application/pdf": "pdf_page",
}
MAX_SOURCE_UPLOAD_BYTES_DEFAULT = 100 * 1024 * 1024


def _guess_mime_type(filename: str, fallback: str | None = None) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or (fallback or "application/octet-stream")


def _max_source_upload_bytes() -> int:
    raw_value = os.getenv("EXPLAINFLOW_MAX_SOURCE_UPLOAD_BYTES", str(MAX_SOURCE_UPLOAD_BYTES_DEFAULT)).strip()
    try:
        parsed = int(raw_value)
    except Exception:
        parsed = MAX_SOURCE_UPLOAD_BYTES_DEFAULT
    return max(parsed, 1024 * 1024)


def _resolve_modality(filename: str, content_type: str | None) -> str:
    normalized = (content_type or "").strip().lower()
    if normalized in _SUPPORTED_EXACT_MIME_TYPES:
        return _SUPPORTED_EXACT_MIME_TYPES[normalized]

    for prefix, modality in _SUPPORTED_MODALITIES.items():
        if normalized.startswith(prefix):
            return modality

    guessed = _guess_mime_type(filename, normalized)
    if guessed in _SUPPORTED_EXACT_MIME_TYPES:
        return _SUPPORTED_EXACT_MIME_TYPES[guessed]
    for prefix, modality in _SUPPORTED_MODALITIES.items():
        if guessed.startswith(prefix):
            return modality

    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported source asset type. Upload image, audio, video, or PDF files only."
        ),
    )


async def ingest_source_upload(
    *,
    request: Request,
    upload: UploadFile,
    descriptor: dict | None = None,
) -> SourceAssetSchema:
    original_name = Path(upload.filename or "source_asset").name
    if not original_name:
        raise HTTPException(status_code=400, detail="Uploaded file is missing a filename.")

    modality = _resolve_modality(original_name, upload.content_type)
    mime_type = _guess_mime_type(original_name, upload.content_type)
    suffix = Path(original_name).suffix.lower()
    if not suffix:
        suffix = ".bin"

    asset_id = f"asset-{modality}-{uuid4().hex[:10]}"
    stored_name = f"{asset_id}{suffix}"
    stored_path = ASSET_DIR / stored_name
    max_size_bytes = _max_source_upload_bytes()
    max_size_mb = max(1, round(max_size_bytes / (1024 * 1024)))

    size_bytes = 0
    try:
        with stored_path.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"{original_name} exceeds the {max_size_mb} MB upload limit.",
                    )
                handle.write(chunk)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if size_bytes == 0:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"{original_name} is empty.")

    metadata = {
        "original_filename": original_name,
        "size_bytes": size_bytes,
    }
    duration_ms = None
    if isinstance(descriptor, dict):
        descriptor_duration = descriptor.get("duration_ms")
        if isinstance(descriptor_duration, (int, float)) and descriptor_duration >= 0:
            duration_ms = int(descriptor_duration)
            metadata["duration_ms"] = duration_ms
    if modality == "pdf_page":
        extracted_text, page_count = _extract_pdf_text(stored_path)
        if extracted_text:
            metadata["normalized_text"] = extracted_text
        if page_count is not None:
            metadata["page_count"] = page_count

    return SourceAssetSchema(
        asset_id=asset_id,
        modality=modality,  # type: ignore[arg-type]
        uri=f"{base_url(request)}/static/assets/{stored_name}",
        mime_type=mime_type,
        title=original_name,
        duration_ms=duration_ms,
        metadata=metadata,
    )


def _extract_pdf_text(path: Path) -> tuple[str, int | None]:
    if PdfReader is None:
        return "", None

    try:
        reader = PdfReader(str(path))
    except Exception:
        return "", None

    page_count = len(reader.pages)
    sections: list[str] = []
    for page in reader.pages[:80]:
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        if text:
            sections.append(text)

    recovered = "\n\n".join(sections).strip()
    if len(recovered) > 40000:
        recovered = recovered[:40000]
    return recovered, page_count


@lru_cache(maxsize=128)
def _extract_pdf_page_text(path_str: str, page_index: int) -> str:
    if PdfReader is None:
        return ""

    try:
        reader = PdfReader(path_str)
    except Exception:
        return ""

    if page_index < 1 or page_index > len(reader.pages):
        return ""

    try:
        return (reader.pages[page_index - 1].extract_text() or "").strip()
    except Exception:
        return ""


@lru_cache(maxsize=32)
def _extract_pdf_pages_text(path_str: str) -> tuple[str, ...]:
    if PdfReader is None:
        return ()

    try:
        reader = PdfReader(path_str)
    except Exception:
        return ()

    pages: list[str] = []
    for page in reader.pages[:200]:
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        pages.append(text)
    return tuple(pages)


def _normalize_match_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).lower()


def _tokenize_match_text(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[A-Za-z0-9']+", _normalize_match_text(text))
        if len(token) >= 3
    ]


def locate_excerpt_in_page_text(
    *,
    page_text: str,
    query_text: str,
) -> dict[str, int | str] | None:
    lines = [line.strip() for line in str(page_text or "").splitlines() if line.strip()]
    query_norm = _normalize_match_text(query_text)
    query_tokens = set(_tokenize_match_text(query_text))
    if not lines or not query_norm or not query_tokens:
        return None

    best_match: tuple[float, int, int, str] | None = None
    max_window = min(4, len(lines))

    for window_size in range(1, max_window + 1):
        for start in range(0, len(lines) - window_size + 1):
            segment_lines = lines[start:start + window_size]
            segment_text = " ".join(segment_lines).strip()
            segment_norm = _normalize_match_text(segment_text)
            if not segment_norm:
                continue

            segment_tokens = set(_tokenize_match_text(segment_text))
            overlap = len(query_tokens & segment_tokens)
            if overlap == 0 and query_norm not in segment_norm and segment_norm not in query_norm:
                continue

            coverage = overlap / max(1, len(query_tokens))
            ratio = SequenceMatcher(None, query_norm, segment_norm).ratio()
            score = coverage * 24.0 + ratio * 12.0 + overlap * 2.5
            if query_norm in segment_norm:
                score += 18.0
            if segment_norm in query_norm and len(segment_norm) > 24:
                score += 8.0
            score -= max(0, window_size - 1) * 0.8

            if best_match is None or score > best_match[0]:
                best_match = (score, start + 1, start + window_size, segment_text)

    if best_match is None or best_match[0] < 8.5:
        return None

    _, line_start, line_end, segment_text = best_match
    excerpt = re.sub(r"\s+", " ", segment_text).strip()
    if len(excerpt) > 280:
        excerpt = excerpt[:277].rsplit(" ", 1)[0].rstrip(" ,.;:") + "..."

    return {
        "line_start": line_start,
        "line_end": line_end,
        "matched_excerpt": excerpt,
    }


def resolve_pdf_proof_locator(
    *,
    asset_ref: str | None,
    page_index: int | None,
    quote_text: str | None = None,
    transcript_text: str | None = None,
    visual_context: str | None = None,
) -> dict[str, int | str] | None:
    if PdfReader is None:
        return None

    source_path = Path(asset_ref).expanduser().resolve() if asset_ref and not str(asset_ref).startswith(("http://", "https://", "/static/")) else None
    if source_path is None:
        try:
            from app.services.image_pipeline import asset_path_from_reference

            source_path = asset_path_from_reference(asset_ref)
        except Exception:
            source_path = None

    if source_path is None or source_path.suffix.lower() != ".pdf":
        return None

    query_candidates = [
        quote_text or "",
        transcript_text or "",
        visual_context or "",
    ]

    def try_page(candidate_page_index: int) -> dict[str, int | str] | None:
        page_text = _extract_pdf_page_text(str(source_path), candidate_page_index)
        if not page_text:
            return None
        for query_text in query_candidates:
            if not str(query_text or "").strip():
                continue
            match = locate_excerpt_in_page_text(page_text=page_text, query_text=query_text)
            if match is not None:
                return {
                    "page_index": candidate_page_index,
                    **match,
                }
        return None

    if page_index is not None and page_index >= 1:
        direct_match = try_page(page_index)
        if direct_match is not None:
            return direct_match

    pages_text = _extract_pdf_pages_text(str(source_path))
    if not pages_text:
        return None

    for resolved_page_index, page_text in enumerate(pages_text, start=1):
        if not page_text:
            continue
        for query_text in query_candidates:
            if not str(query_text or "").strip():
                continue
            match = locate_excerpt_in_page_text(page_text=page_text, query_text=query_text)
            if match is not None:
                return {
                    "page_index": resolved_page_index,
                    **match,
                }

    return None


def best_effort_manifest_text(source_manifest: SourceManifestSchema | dict | None) -> tuple[str, str | None]:
    if source_manifest is None:
        return "", None

    manifest: SourceManifestSchema
    if isinstance(source_manifest, SourceManifestSchema):
        manifest = source_manifest
    elif isinstance(source_manifest, dict):
        try:
            manifest = SourceManifestSchema.model_validate(source_manifest)
        except Exception:
            return "", None
    else:
        return "", None

    sections: list[str] = []
    for asset in manifest.assets[:8]:
        text_candidates = [
            asset.transcript_text,
            asset.ocr_text,
        ]
        if isinstance(asset.metadata, dict):
            for key in ("normalized_text", "extracted_text", "text", "text_preview"):
                candidate = str(asset.metadata.get(key, "")).strip()
                if candidate:
                    text_candidates.append(candidate)

        recovered = next((candidate.strip() for candidate in text_candidates if isinstance(candidate, str) and candidate.strip()), "")
        if not recovered:
            continue

        sections.append(recovered)

    if not sections:
        return "", None

    return "\n\n".join(sections).strip(), "asset_embedded_text"


def validate_video_manifest_constraints(
    *,
    source_manifest: SourceManifestSchema | dict | None,
    source_text: str = "",
    normalized_source_text: str = "",
) -> str | None:
    if source_manifest is None:
        return None

    manifest: SourceManifestSchema
    if isinstance(source_manifest, SourceManifestSchema):
        manifest = source_manifest
    elif isinstance(source_manifest, dict):
        try:
            manifest = SourceManifestSchema.model_validate(source_manifest)
        except Exception:
            return None
    else:
        return None

    has_transcript_layer = bool(str(source_text or "").strip()) or bool(str(normalized_source_text or "").strip())

    def _is_remote_youtube_asset(asset: SourceAssetSchema) -> bool:
        raw_uri = str(asset.uri or "").strip()
        if not raw_uri:
            return False
        try:
            host = urlparse(raw_uri).netloc.lower()
        except Exception:
            return False
        return any(domain in host for domain in ("youtube.com", "youtu.be", "youtube-nocookie.com"))

    for asset in manifest.assets:
        if asset.modality != "video":
            continue
        asset_has_transcript = has_transcript_layer or bool(str(asset.transcript_text or "").strip())
        duration_ms = asset.duration_ms
        if duration_ms is None and isinstance(asset.metadata, dict):
            raw_duration = asset.metadata.get("duration_ms")
            if isinstance(raw_duration, (int, float)) and raw_duration >= 0:
                duration_ms = int(raw_duration)

        if duration_ms is None:
            if _is_remote_youtube_asset(asset) and asset_has_transcript:
                continue
            return (
                "Video uploads require readable duration metadata. Re-upload from a browser that can read the clip "
                "duration, or provide the content as text/transcript instead."
            )
        if duration_ms > 10 * 60 * 1000:
            return "Video uploads are currently limited to 10 minutes."
        if duration_ms > 2 * 60 * 1000 and not asset_has_transcript:
            return (
                "Videos longer than 2 minutes require transcript or captions. Paste the transcript into Document Text "
                "or attach a video asset that already contains transcript text."
            )
    return None
