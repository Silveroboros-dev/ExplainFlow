import time
from io import BytesIO
from pathlib import Path
import re
import os
from threading import Lock
from urllib.parse import urlparse

from fastapi import Request
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from google.cloud import storage

from app.config import ASSET_DIR, BUCKET_NAME


_STORAGE_BUCKET: storage.Bucket | None = None
_STORAGE_BUCKET_LOCK = Lock()


def base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def asset_path_from_url(asset_url: str | None) -> Path | None:
    if not asset_url:
        return None

    parsed = urlparse(asset_url)
    asset_name = Path(parsed.path).name
    if not asset_name:
        return None

    candidate = ASSET_DIR / asset_name
    if not candidate.exists() or not candidate.is_file():
        return None

    try:
        candidate.resolve().relative_to(ASSET_DIR.resolve())
    except Exception:
        return None

    return candidate


def asset_path_from_reference(asset_ref: str | None) -> Path | None:
    if not asset_ref:
        return None

    url_candidate = asset_path_from_url(asset_ref)
    if url_candidate is not None:
        return url_candidate

    try:
        path_candidate = Path(asset_ref).expanduser().resolve()
    except Exception:
        return None

    if not path_candidate.exists() or not path_candidate.is_file():
        return None

    try:
        path_candidate.relative_to(ASSET_DIR.resolve())
    except Exception:
        return None

    return path_candidate


def public_asset_url(request: Request, asset_uri: str | None) -> str:
    if not asset_uri:
        return ""

    candidate = str(asset_uri).strip()
    if not candidate:
        return ""

    local_path = asset_path_from_reference(candidate)
    if local_path is not None:
        return f"{base_url(request)}/static/assets/{local_path.name}"

    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate

    if candidate.startswith("/static/"):
        return f"{base_url(request)}{candidate}"

    return candidate


def _get_storage_bucket() -> storage.Bucket | None:
    global _STORAGE_BUCKET

    if not BUCKET_NAME:
        return None
    if _STORAGE_BUCKET is not None:
        return _STORAGE_BUCKET

    with _STORAGE_BUCKET_LOCK:
        if _STORAGE_BUCKET is None:
            storage_client = storage.Client()
            _STORAGE_BUCKET = storage_client.bucket(BUCKET_NAME)
    return _STORAGE_BUCKET


def save_image_and_get_url(request: Request, scene_id: str, image_bytes: bytes, prefix: str) -> str:
    ts = int(time.time() * 1000)
    img_filename = f"{prefix}_{scene_id}_{ts}.png"
    
    # Save locally first (as backup and for immediate processing if needed)
    img_path = ASSET_DIR / img_filename
    img_path.write_bytes(image_bytes)

    # If GCS bucket is configured, upload and return GCS URL
    if BUCKET_NAME:
        try:
            bucket = _get_storage_bucket()
            if bucket is None:
                raise RuntimeError("Storage bucket is unavailable.")
            blob = bucket.blob(img_filename)
            blob.upload_from_string(image_bytes, content_type="image/png")
            return f"https://storage.googleapis.com/{BUCKET_NAME}/{img_filename}"
        except Exception as exc:
            print(f"GCS upload failed for {img_filename}: {exc}")
            # Fallback to local URL if GCS fails
    
    return f"{base_url(request)}/static/assets/{img_filename}"


def crop_source_region_and_get_url(
    request: Request,
    *,
    scene_id: str,
    source_ref: str,
    bbox_norm: list[float],
    prefix: str,
) -> str:
    if len(bbox_norm) != 4:
        raise ValueError("bbox_norm must contain four values.")

    x1, y1, x2, y2 = [float(value) for value in bbox_norm]
    x1 = max(0.0, min(1.0, x1))
    y1 = max(0.0, min(1.0, y1))
    x2 = max(0.0, min(1.0, x2))
    y2 = max(0.0, min(1.0, y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("bbox_norm must define a positive crop region.")

    source_path = asset_path_from_reference(source_ref)
    if source_path is None:
        raise FileNotFoundError(f"Unable to resolve source region for {scene_id}.")

    with Image.open(source_path) as raw_image:
        image = ImageOps.exif_transpose(raw_image).convert("RGBA")
        width, height = image.size
        left = int(round(width * x1))
        top = int(round(height * y1))
        right = int(round(width * x2))
        bottom = int(round(height * y2))
        if right <= left or bottom <= top:
            raise ValueError("Resolved crop region is empty.")

        cropped = image.crop((left, top, right, bottom))
        buffer = BytesIO()
        cropped.save(buffer, format="PNG", optimize=True)

    return save_image_and_get_url(
        request=request,
        scene_id=scene_id,
        image_bytes=buffer.getvalue(),
        prefix=prefix,
    )


_BOLD_FONT_CANDIDATES = (
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

_REGULAR_FONT_CANDIDATES = (
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Verdana.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _load_font(*, size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = _BOLD_FONT_CANDIDATES if bold else _REGULAR_FONT_CANDIDATES
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _truncate_phrase(text: str, *, max_words: int, max_chars: int) -> str:
    cleaned = _normalize_spaces(text).strip(" .,:;")
    if not cleaned:
        return ""
    words = cleaned.split(" ")
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words]).strip()
    if len(cleaned) > max_chars:
        trimmed = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
        cleaned = trimmed or cleaned[:max_chars].strip()
    if len(words) > max_words or len(text) > len(cleaned):
        return cleaned.rstrip(" .,:;") + "..."
    return cleaned.rstrip(" .,:;")


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = _normalize_spaces(text).split(" ")
    if not words or not words[0]:
        return []

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
            continue
        lines.append(current)
        current = word

    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return [line.strip() for line in lines if line.strip()]

    clipped = lines[:max_lines]
    last_line = clipped[-1]
    while last_line and draw.textlength(f"{last_line}...", font=font) > max_width:
        if " " not in last_line:
            last_line = last_line[:-1]
        else:
            last_line = last_line.rsplit(" ", 1)[0]
    clipped[-1] = last_line.rstrip(" .,:;") + "..."
    return [line.strip() for line in clipped if line.strip()]


def _fit_wrapped_text(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    max_width: int,
    max_height: int,
    max_lines: int,
    start_size: int,
    min_size: int,
    bold: bool,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int]:
    for size in range(start_size, min_size - 1, -2):
        font = _load_font(size=size, bold=bold)
        lines = _wrap_text(draw, text=text, font=font, max_width=max_width, max_lines=max_lines)
        if not lines:
            continue
        spacing = max(6, size // 4)
        bbox = draw.multiline_textbbox((0, 0), "\n".join(lines), font=font, spacing=spacing)
        if bbox[2] - bbox[0] <= max_width and bbox[3] - bbox[1] <= max_height:
            return font, lines, spacing

    font = _load_font(size=max(min_size, 12), bold=bold)
    lines = _wrap_text(draw, text=text, font=font, max_width=max_width, max_lines=max_lines)
    spacing = max(6, min_size // 4)
    return font, lines, spacing


def _derive_cover_subtitle(*, title: str, support_text: str) -> str:
    cleaned_support = _normalize_spaces(support_text)
    if not cleaned_support:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", cleaned_support)
    title_tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9']+", title) if token}

    for sentence in sentences:
        candidate = _truncate_phrase(sentence, max_words=16, max_chars=110)
        if not candidate:
            continue
        candidate_tokens = {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9']+", candidate)
            if token
        }
        overlap = len(title_tokens & candidate_tokens)
        if title_tokens and candidate_tokens and overlap / max(1, min(len(title_tokens), len(candidate_tokens))) > 0.6:
            continue
        return candidate
    return ""


def build_thumbnail_cover_cues(
    *,
    title: str,
    claim_text_snippets: list[str] | None = None,
    support_text: str = "",
    max_cues: int = 2,
) -> list[str]:
    title_tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9']+", title)
        if token
    }
    cues: list[str] = []
    seen: set[str] = set()
    candidates = list(claim_text_snippets or [])
    if support_text:
        candidates.append(support_text)

    for candidate in candidates:
        phrase = _normalize_spaces(str(candidate or ""))
        if not phrase:
            continue
        phrase = re.split(r"[.;:!?]", phrase, maxsplit=1)[0]
        phrase = re.sub(r"^(this|that|these|those|there is|there are)\s+", "", phrase, flags=re.IGNORECASE)
        short = _truncate_phrase(phrase, max_words=7, max_chars=42)
        if not short:
            continue
        cue_key = short.lower()
        if cue_key in seen:
            continue
        cue_tokens = {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9']+", short)
            if token
        }
        if title_tokens and cue_tokens and len(title_tokens & cue_tokens) / max(1, min(len(title_tokens), len(cue_tokens))) > 0.7:
            continue
        seen.add(cue_key)
        cues.append(short)
        if len(cues) >= max_cues:
            break

    return cues


def compose_thumbnail_cover_and_get_url(
    request: Request,
    *,
    scene_id: str,
    source_url: str,
    title: str,
    support_text: str = "",
    cue_lines: list[str] | None = None,
    prefix: str,
) -> str:
    source_path = asset_path_from_url(source_url)
    if source_path is None:
        raise FileNotFoundError(f"Unable to resolve source image for {scene_id}.")

    with Image.open(source_path) as raw_image:
        image = ImageOps.exif_transpose(raw_image).convert("RGBA")
        width, height = image.size
        if width <= 0 or height <= 0:
            raise ValueError(f"Source image for {scene_id} has invalid dimensions.")

        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        scrim_width = int(width * 0.5)
        scrim_color = (6, 16, 30)
        scrim = Image.new("RGBA", (scrim_width, height), (*scrim_color, 0))
        alpha_mask = Image.new("L", (scrim_width, height), 0)
        alpha_draw = ImageDraw.Draw(alpha_mask)
        for x in range(scrim_width):
            strength = 1.0 - (x / max(1, scrim_width - 1))
            alpha = int(230 * (strength ** 1.8))
            alpha_draw.line((x, 0, x, height), fill=alpha)
        scrim.putalpha(alpha_mask)
        overlay.alpha_composite(scrim, (0, 0))

        margin_x = int(width * 0.055)
        cursor_y = int(height * 0.08)
        text_width = int(width * 0.34)

        accent_height = max(6, height // 120)
        accent_width = int(width * 0.09)
        overlay_draw.rounded_rectangle(
            (margin_x, cursor_y, margin_x + accent_width, cursor_y + accent_height),
            radius=max(3, accent_height // 2),
            fill=(102, 177, 255, 245),
        )
        cursor_y += accent_height + max(18, height // 42)

        kicker_font = _load_font(size=max(16, width // 55), bold=True)
        overlay_draw.text(
            (margin_x, cursor_y),
            "EXPLAINFLOW",
            font=kicker_font,
            fill=(192, 220, 255, 235),
        )
        kicker_bbox = overlay_draw.textbbox((margin_x, cursor_y), "EXPLAINFLOW", font=kicker_font)
        cursor_y = kicker_bbox[3] + max(16, height // 45)

        title_font, title_lines, title_spacing = _fit_wrapped_text(
            overlay_draw,
            text=title,
            max_width=text_width,
            max_height=int(height * 0.32),
            max_lines=4,
            start_size=max(36, width // 16),
            min_size=max(24, width // 30),
            bold=True,
        )
        overlay_draw.multiline_text(
            (margin_x, cursor_y),
            "\n".join(title_lines),
            font=title_font,
            fill=(249, 250, 251, 255),
            spacing=title_spacing,
        )
        title_bbox = overlay_draw.multiline_textbbox(
            (margin_x, cursor_y),
            "\n".join(title_lines),
            font=title_font,
            spacing=title_spacing,
        )
        cursor_y = title_bbox[3] + max(16, height // 48)

        subtitle = _derive_cover_subtitle(title=title, support_text=support_text)
        if subtitle:
            subtitle_font, subtitle_lines, subtitle_spacing = _fit_wrapped_text(
                overlay_draw,
                text=subtitle,
                max_width=text_width,
                max_height=int(height * 0.12),
                max_lines=2,
                start_size=max(20, width // 36),
                min_size=max(16, width // 50),
                bold=False,
            )
            overlay_draw.multiline_text(
                (margin_x, cursor_y),
                "\n".join(subtitle_lines),
                font=subtitle_font,
                fill=(214, 226, 242, 232),
                spacing=subtitle_spacing,
            )

        cue_texts = [
            _truncate_phrase(cue, max_words=7, max_chars=42)
            for cue in (cue_lines or [])
            if _normalize_spaces(cue)
        ]
        cue_texts = [cue for cue in cue_texts if cue]

        if cue_texts:
            cue_font = _load_font(size=max(16, width // 50), bold=True)
            chip_padding_x = max(12, width // 90)
            chip_padding_y = max(8, height // 90)
            chip_gap = max(10, height // 80)
            bottom_y = height - int(height * 0.08)

            for cue in reversed(cue_texts[:2]):
                text_bbox = overlay_draw.textbbox((0, 0), cue, font=cue_font)
                chip_width = min(text_width, (text_bbox[2] - text_bbox[0]) + chip_padding_x * 2)
                chip_height = (text_bbox[3] - text_bbox[1]) + chip_padding_y * 2
                top_y = bottom_y - chip_height
                overlay_draw.rounded_rectangle(
                    (margin_x, top_y, margin_x + chip_width, bottom_y),
                    radius=max(12, chip_height // 2),
                    fill=(255, 255, 255, 38),
                    outline=(255, 255, 255, 64),
                    width=1,
                )
                overlay_draw.text(
                    (margin_x + chip_padding_x, top_y + chip_padding_y - 1),
                    cue,
                    font=cue_font,
                    fill=(248, 250, 252, 255),
                )
                bottom_y = top_y - chip_gap

        composed = Image.alpha_composite(image, overlay)
        buffer = BytesIO()
        composed.save(buffer, format="PNG", optimize=True)

    return save_image_and_get_url(
        request=request,
        scene_id=scene_id,
        image_bytes=buffer.getvalue(),
        prefix=prefix,
    )


def upscale_image_and_get_url(
    request: Request,
    *,
    scene_id: str,
    source_url: str,
    prefix: str,
    scale_factor: int = 2,
) -> str:
    if scale_factor not in {2, 4}:
        raise ValueError("scale_factor must be 2 or 4.")

    source_path = asset_path_from_url(source_url)
    if source_path is None:
        raise FileNotFoundError(f"Unable to resolve source image for {scene_id}.")

    with Image.open(source_path) as raw_image:
        image = ImageOps.exif_transpose(raw_image)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA")

        width, height = image.size
        if width <= 0 or height <= 0:
            raise ValueError(f"Source image for {scene_id} has invalid dimensions.")

        upscaled = image.resize(
            (width * scale_factor, height * scale_factor),
            resample=Image.Resampling.LANCZOS,
        )
        upscaled = upscaled.filter(ImageFilter.UnsharpMask(radius=1.2, percent=125, threshold=3))

        buffer = BytesIO()
        upscaled.save(buffer, format="PNG", optimize=True)

    return save_image_and_get_url(
        request=request,
        scene_id=scene_id,
        image_bytes=buffer.getvalue(),
        prefix=prefix,
    )
