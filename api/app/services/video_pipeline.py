from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import Request
from PIL import Image, ImageDraw, ImageFont

from app.config import ASSET_DIR
from app.schemas.requests import (
    QuickArtifactSchema,
    QuickVideoSchema,
    QuickVideoSegmentSchema,
    SourceAssetSchema,
    SourceManifestSchema,
)
from app.services.audio_pipeline import generate_audio_and_get_url
from app.services.image_pipeline import asset_path_from_reference, base_url, public_asset_url, save_image_and_get_url


VIDEO_SIZE = (1280, 720)
VIDEO_FPS = 24
VIDEO_CROSSFADE_SEC = 0.35
DEFAULT_PROOF_CLIP_SEC = 4.0
DEFAULT_MIN_SEGMENT_SEC = 2.5
MAX_SEGMENT_PROOF_SEC = 5.0
MIN_SEGMENT_PROOF_SEC = 3.0
QUICK_VIDEO_PLAYBACK_RATE = 1.1

_BOLD_FONT_CANDIDATES = (
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
_REGULAR_FONT_CANDIDATES = (
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _source_manifest_model(source_manifest: SourceManifestSchema | dict[str, Any] | None) -> SourceManifestSchema | None:
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


def _source_asset_lookup(source_manifest: SourceManifestSchema | dict[str, Any] | None) -> dict[str, SourceAssetSchema]:
    manifest = _source_manifest_model(source_manifest)
    if manifest is None:
        return {}
    return {
        asset.asset_id: asset
        for asset in manifest.assets
        if isinstance(asset.asset_id, str) and asset.asset_id.strip()
    }


def _load_font(*, size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = _BOLD_FONT_CANDIDATES if bold else _REGULAR_FONT_CANDIDATES
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = text.strip().split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines - 1:
            break

    if len(lines) < max_lines and current:
        lines.append(current)

    remaining_words = words[len(" ".join(lines).split()):]
    if remaining_words and lines:
        lines[-1] = lines[-1].rstrip(" .,:;") + "..."
    return lines[:max_lines]


def _estimate_voiceover_duration_ms(text: str) -> int:
    words = max(1, len(text.strip().split()))
    seconds = max(DEFAULT_MIN_SEGMENT_SEC, (words / 2.5) + 0.5)
    return int(round(seconds * 1000))


def _audio_duration_ms(audio_path: Path | None) -> int | None:
    if audio_path is None:
        return None

    try:
        from moviepy import AudioFileClip
    except Exception:
        return None

    audio_clip = None
    try:
        audio_clip = AudioFileClip(str(audio_path))
        duration_sec = float(audio_clip.duration or 0.0)
        if duration_sec <= 0:
            return None
        return int(round(duration_sec * 1000))
    except Exception:
        return None
    finally:
        if audio_clip is not None:
            try:
                audio_clip.close()
            except Exception:
                pass


def _render_placeholder_image_url(
    *,
    request: Request,
    segment_id: str,
    title: str,
    caption_text: str,
) -> str:
    canvas = Image.new("RGB", VIDEO_SIZE, (10, 14, 24))
    draw = ImageDraw.Draw(canvas)

    title_font = _load_font(size=54, bold=True)
    body_font = _load_font(size=30, bold=False)
    badge_font = _load_font(size=20, bold=True)

    draw.rounded_rectangle((80, 72, 360, 122), radius=26, fill=(30, 41, 59))
    draw.text((110, 87), "Quick MP4", fill=(226, 232, 240), font=badge_font)
    draw.text((80, 170), title.strip() or "Proof Segment", fill=(248, 250, 252), font=title_font)

    wrapped_caption = _wrap_text(
        draw,
        text=caption_text.strip() or title.strip() or "Proof segment",
        font=body_font,
        max_width=VIDEO_SIZE[0] - 160,
        max_lines=4,
    )
    y = 270
    for line in wrapped_caption:
        draw.text((80, y), line, fill=(203, 213, 225), font=body_font)
        y += 48

    accent_y = VIDEO_SIZE[1] - 96
    draw.rounded_rectangle((80, accent_y, VIDEO_SIZE[0] - 80, accent_y + 8), radius=4, fill=(59, 130, 246))

    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True)
    return save_image_and_get_url(
        request=request,
        scene_id=segment_id,
        image_bytes=buffer.getvalue(),
        prefix="quick_video_placeholder",
    )


def _proof_image_url(
    *,
    request: Request,
    segment: QuickReelSegmentSchema,
    asset_lookup: dict[str, SourceAssetSchema],
) -> str | None:
    primary_media = segment.primary_media
    if primary_media is None or primary_media.modality not in {"image", "pdf_page"}:
        return None
    asset = asset_lookup.get(primary_media.asset_id)
    if asset is None:
        return None
    candidate_url = public_asset_url(request, asset.uri)
    if not candidate_url or asset_path_from_reference(candidate_url) is None:
        return None
    return candidate_url


def _proof_video_payload(
    *,
    request: Request,
    segment: QuickReelSegmentSchema,
    asset_lookup: dict[str, SourceAssetSchema],
) -> tuple[str | None, int | None, int | None]:
    primary_media = segment.primary_media
    if primary_media is None or primary_media.modality != "video":
        return None, None, None

    asset = asset_lookup.get(primary_media.asset_id)
    if asset is None:
        return None, None, None

    candidate_url = public_asset_url(request, asset.uri)
    if not candidate_url or asset_path_from_reference(candidate_url) is None:
        return None, None, None

    start_ms = primary_media.start_ms if primary_media.start_ms is not None else 0
    end_ms = primary_media.end_ms
    asset_duration_ms = asset.duration_ms if asset.duration_ms is not None and asset.duration_ms > 0 else None

    if end_ms is None or end_ms <= start_ms:
        fallback_end = start_ms + int(DEFAULT_PROOF_CLIP_SEC * 1000)
        if asset_duration_ms is not None:
            end_ms = min(asset_duration_ms, fallback_end)
        else:
            end_ms = fallback_end

    clip_duration_ms = max(0, end_ms - start_ms)
    if clip_duration_ms == 0:
        if asset_duration_ms is not None and asset_duration_ms > start_ms:
            end_ms = min(asset_duration_ms, start_ms + int(DEFAULT_PROOF_CLIP_SEC * 1000))
            clip_duration_ms = max(0, end_ms - start_ms)
        else:
            return None, None, None

    if clip_duration_ms < int(MIN_SEGMENT_PROOF_SEC * 1000):
        desired_end = start_ms + int(MIN_SEGMENT_PROOF_SEC * 1000)
        if asset_duration_ms is not None:
            end_ms = min(asset_duration_ms, desired_end)
        else:
            end_ms = desired_end
    elif clip_duration_ms > int(MAX_SEGMENT_PROOF_SEC * 1000):
        end_ms = start_ms + int(MAX_SEGMENT_PROOF_SEC * 1000)

    if asset_duration_ms is not None:
        end_ms = min(end_ms, asset_duration_ms)

    if end_ms <= start_ms:
        return None, None, None

    return candidate_url, start_ms, end_ms


def build_quick_video_segment(
    *,
    request: Request,
    artifact: QuickArtifactSchema,
    segment: QuickReelSegmentSchema,
    source_manifest: SourceManifestSchema | dict[str, Any] | None,
) -> QuickVideoSegmentSchema:
    asset_lookup = _source_asset_lookup(source_manifest)
    artifact_block = next(
        (block for block in artifact.blocks if block.block_id == segment.block_id),
        None,
    )
    voiceover_url = generate_audio_and_get_url(
        request=request,
        scene_id=segment.segment_id,
        text=segment.caption_text,
        prefix="quick_video_voiceover",
        playback_rate=QUICK_VIDEO_PLAYBACK_RATE,
    )
    voiceover_path = asset_path_from_reference(voiceover_url)
    voiceover_duration_ms = _audio_duration_ms(voiceover_path) or _estimate_voiceover_duration_ms(segment.caption_text)

    visual_url = (
        (segment.fallback_image_url or "").strip()
        or ((artifact_block.image_url or "").strip() if artifact_block is not None else "")
        or None
    )
    if not visual_url:
        visual_url = _proof_image_url(
            request=request,
            segment=segment,
            asset_lookup=asset_lookup,
        )

    source_video_url, source_start_ms, source_end_ms = _proof_video_payload(
        request=request,
        segment=segment,
        asset_lookup=asset_lookup,
    )

    if source_video_url and visual_url:
        render_mode = "image_plus_clip"
        proof_duration_ms = max(0, (source_end_ms or 0) - (source_start_ms or 0))
        duration_ms = voiceover_duration_ms + proof_duration_ms
    elif source_video_url:
        render_mode = "clip_only"
        proof_duration_ms = max(0, (source_end_ms or 0) - (source_start_ms or 0))
        duration_ms = max(voiceover_duration_ms, proof_duration_ms)
    else:
        render_mode = "image_only"
        duration_ms = voiceover_duration_ms

    if not visual_url and render_mode != "clip_only":
        visual_url = _render_placeholder_image_url(
            request=request,
            segment_id=segment.segment_id,
            title=segment.title,
            caption_text=segment.caption_text,
        )

    if not voiceover_url:
        voiceover_url = None

    return QuickVideoSegmentSchema(
        segment_id=segment.segment_id,
        block_id=segment.block_id,
        title=segment.title,
        caption_text=segment.caption_text,
        voiceover_url=voiceover_url,
        visual_url=visual_url,
        source_video_url=source_video_url,
        source_start_ms=source_start_ms,
        source_end_ms=source_end_ms,
        duration_ms=duration_ms,
        render_mode=render_mode,
    )


def _extend_clip_to_duration(
    *,
    clip: Any,
    target_duration_sec: float,
    concatenate_videoclips: Any,
    created_clips: list[Any],
) -> Any:
    duration_sec = float(getattr(clip, "duration", 0.0) or 0.0)
    if target_duration_sec <= 0:
        return clip
    if duration_sec <= 0:
        return clip
    if duration_sec >= target_duration_sec:
        trimmed = clip.subclipped(0, target_duration_sec)
        created_clips.append(trimmed)
        return trimmed

    freeze_frame = clip.to_ImageClip(
        t=max(duration_sec - 0.05, 0.0),
        duration=target_duration_sec - duration_sec,
    )
    created_clips.append(freeze_frame)
    extended = concatenate_videoclips([clip, freeze_frame], method="compose")
    created_clips.append(extended)
    return extended


def _image_clip_for_segment(
    *,
    image_path: Path,
    duration_sec: float,
    CompositeVideoClip: Any,
    ImageClip: Any,
    vfx: Any,
    created_clips: list[Any],
) -> Any:
    base_clip = ImageClip(str(image_path))
    created_clips.append(base_clip)
    width = float(getattr(base_clip, "w", VIDEO_SIZE[0]) or VIDEO_SIZE[0])
    height = float(getattr(base_clip, "h", VIDEO_SIZE[1]) or VIDEO_SIZE[1])
    base_scale = max(VIDEO_SIZE[0] / max(width, 1.0), VIDEO_SIZE[1] / max(height, 1.0))
    zoom_clip = base_clip.with_duration(duration_sec).with_effects(
        [
            vfx.Resize(
                lambda t: base_scale * (1.0 + (0.12 * (t / max(duration_sec, 0.001))))
            )
        ]
    ).with_position("center")
    created_clips.append(zoom_clip)
    composed = CompositeVideoClip([zoom_clip], size=VIDEO_SIZE).with_duration(duration_sec)
    created_clips.append(composed)
    return composed


def _video_clip_for_segment(
    *,
    video_path: Path,
    start_sec: float,
    end_sec: float,
    VideoFileClip: Any,
    CompositeVideoClip: Any,
    vfx: Any,
    created_clips: list[Any],
) -> Any:
    base_clip = VideoFileClip(str(video_path), audio=False)
    created_clips.append(base_clip)
    proof_clip = base_clip.subclipped(start_sec, end_sec).without_audio()
    created_clips.append(proof_clip)
    width = float(getattr(proof_clip, "w", VIDEO_SIZE[0]) or VIDEO_SIZE[0])
    height = float(getattr(proof_clip, "h", VIDEO_SIZE[1]) or VIDEO_SIZE[1])
    base_scale = max(VIDEO_SIZE[0] / max(width, 1.0), VIDEO_SIZE[1] / max(height, 1.0))
    scaled_clip = proof_clip.with_effects([vfx.Resize(base_scale)]).with_position("center")
    created_clips.append(scaled_clip)
    composed = CompositeVideoClip([scaled_clip], size=VIDEO_SIZE).with_duration(float(proof_clip.duration or 0.0))
    created_clips.append(composed)
    return composed


def render_quick_video_mp4(
    *,
    request: Request,
    artifact: QuickArtifactSchema,
    video: QuickVideoSchema,
) -> tuple[str, int]:
    try:
        from moviepy import (
            AudioClip,
            AudioFileClip,
            CompositeVideoClip,
            ImageClip,
            VideoFileClip,
            concatenate_videoclips,
            vfx,
        )
    except Exception as exc:
        raise RuntimeError(f"MoviePy is unavailable: {exc}") from exc

    segment_clips: list[Any] = []
    created_clips: list[Any] = []

    try:
        for segment in video.segments:
            voiceover_path = asset_path_from_reference(segment.voiceover_url)
            voiceover_clip = None
            voiceover_duration_sec = max(
                DEFAULT_MIN_SEGMENT_SEC,
                (segment.duration_ms or _estimate_voiceover_duration_ms(segment.caption_text)) / 1000.0,
            )
            if voiceover_path is not None:
                try:
                    voiceover_clip = AudioFileClip(str(voiceover_path))
                    created_clips.append(voiceover_clip)
                    if getattr(voiceover_clip, "duration", 0):
                        voiceover_duration_sec = max(DEFAULT_MIN_SEGMENT_SEC, float(voiceover_clip.duration))
                except Exception:
                    voiceover_clip = None

            visual_path = asset_path_from_reference(segment.visual_url)
            source_video_path = asset_path_from_reference(segment.source_video_url)

            if (
                segment.render_mode != "clip_only"
                and segment.visual_url
                and visual_path is None
            ):
                raise RuntimeError(
                    f"Quick video is missing the rendered image asset for block {segment.block_id}. "
                    "Regenerate the Quick artifact before exporting MP4."
                )

            image_clip = None
            if visual_path is not None:
                image_clip = _image_clip_for_segment(
                    image_path=visual_path,
                    duration_sec=voiceover_duration_sec,
                    CompositeVideoClip=CompositeVideoClip,
                    ImageClip=ImageClip,
                    vfx=vfx,
                    created_clips=created_clips,
                )
            elif segment.render_mode != "clip_only":
                placeholder_url = _render_placeholder_image_url(
                    request=request,
                    segment_id=segment.segment_id,
                    title=segment.title,
                    caption_text=segment.caption_text,
                )
                placeholder_path = asset_path_from_reference(placeholder_url)
                if placeholder_path is not None:
                    image_clip = _image_clip_for_segment(
                        image_path=placeholder_path,
                        duration_sec=voiceover_duration_sec,
                        CompositeVideoClip=CompositeVideoClip,
                        ImageClip=ImageClip,
                        vfx=vfx,
                        created_clips=created_clips,
                    )

            image_with_audio = None
            if image_clip is not None:
                if voiceover_clip is not None:
                    image_with_audio = image_clip.with_audio(voiceover_clip)
                else:
                    silent_audio = AudioClip(lambda t: 0.0, duration=voiceover_duration_sec, fps=44100)
                    created_clips.append(silent_audio)
                    image_with_audio = image_clip.with_audio(silent_audio)
                created_clips.append(image_with_audio)

            proof_clip = None
            if (
                source_video_path is not None
                and segment.source_start_ms is not None
                and segment.source_end_ms is not None
                and segment.source_end_ms > segment.source_start_ms
            ):
                proof_clip = _video_clip_for_segment(
                    video_path=source_video_path,
                    start_sec=segment.source_start_ms / 1000.0,
                    end_sec=segment.source_end_ms / 1000.0,
                    VideoFileClip=VideoFileClip,
                    CompositeVideoClip=CompositeVideoClip,
                    vfx=vfx,
                    created_clips=created_clips,
                )

            if segment.render_mode == "clip_only" and proof_clip is not None:
                clip_only = _extend_clip_to_duration(
                    clip=proof_clip,
                    target_duration_sec=voiceover_duration_sec,
                    concatenate_videoclips=concatenate_videoclips,
                    created_clips=created_clips,
                )
                if voiceover_clip is not None:
                    clip_only = clip_only.with_audio(voiceover_clip)
                created_clips.append(clip_only)
                segment_clip = clip_only
            elif proof_clip is not None and segment.render_mode == "image_plus_clip" and image_with_audio is not None:
                segment_clip = concatenate_videoclips([image_with_audio, proof_clip], method="compose")
                created_clips.append(segment_clip)
            elif image_with_audio is not None:
                segment_clip = image_with_audio
            else:
                raise RuntimeError(f"Quick video segment {segment.segment_id} has no renderable visual media.")

            segment_clips.append(segment_clip)

        if not segment_clips:
            raise RuntimeError("No renderable Quick video segments were produced.")

        final_clip = concatenate_videoclips(
            segment_clips,
            method="compose",
            padding=-VIDEO_CROSSFADE_SEC,
        )
        created_clips.append(final_clip)

        ts = int(time.time() * 1000)
        output_name = f"quick_video_{artifact.artifact_id}_{ts}.mp4"
        output_path = ASSET_DIR / output_name
        final_clip.write_videofile(
            str(output_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        duration_ms = int(round(float(getattr(final_clip, "duration", 0.0) or 0.0) * 1000))
        return f"{base_url(request)}/static/assets/{output_name}", duration_ms
    finally:
        for clip in reversed(created_clips):
            try:
                clip.close()
            except Exception:
                continue


def build_quick_video(
    *,
    request: Request,
    artifact: QuickArtifactSchema,
    source_manifest: SourceManifestSchema | dict[str, Any] | None,
) -> QuickVideoSchema:
    if artifact.reel is None or not artifact.reel.segments:
        raise ValueError("Quick artifact reel is required before generating a video.")

    segments = [
        build_quick_video_segment(
            request=request,
            artifact=artifact,
            segment=segment,
            source_manifest=source_manifest,
        )
        for segment in artifact.reel.segments
    ]

    video = QuickVideoSchema(
        video_id=f"{artifact.artifact_id}-video-{int(time.time())}",
        video_url="",
        duration_ms=sum(int(segment.duration_ms or 0) for segment in segments) or None,
        segments=segments,
    )
    video_url, duration_ms = render_quick_video_mp4(
        request=request,
        artifact=artifact,
        video=video,
    )
    return video.model_copy(update={"video_url": video_url, "duration_ms": duration_ms})
