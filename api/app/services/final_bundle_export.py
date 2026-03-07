from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from app.config import ASSET_DIR
from app.schemas.requests import FinalBundleSceneAsset


def _slugify(value: str, fallback: str) -> str:
    lowered = value.strip().lower()
    slug = "".join(char if char.isalnum() else "-" for char in lowered)
    collapsed = "-".join(part for part in slug.split("-") if part)
    return collapsed or fallback


def _scene_order(scene_id: str) -> tuple[int, str]:
    lowered = scene_id.lower()
    if lowered.startswith("scene-"):
        suffix = lowered.split("scene-", 1)[1]
        if suffix.isdigit():
            return (int(suffix), lowered)
    return (10_000, lowered)


def _safe_scene_stem(scene: FinalBundleSceneAsset, index: int) -> str:
    base = scene.scene_id.strip() or f"scene-{index}"
    slug = _slugify(base, f"scene-{index}")
    return f"{index:02d}-{slug}"


def _asset_path_from_url(asset_url: str | None) -> Path | None:
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


def _transcript_for_scenes(scenes: list[FinalBundleSceneAsset]) -> str:
    chunks: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        title = (scene.title or "").strip() or f"Scene {index}"
        chunks.append(f"Scene {index}: {title}\n\n{scene.text.strip()}")
    return "\n\n---\n\n".join(chunks).strip() + "\n"


def build_final_bundle_zip(
    *,
    topic: str,
    scenes: list[FinalBundleSceneAsset],
) -> tuple[str, bytes]:
    ordered_scenes = sorted(scenes, key=lambda scene: _scene_order(scene.scene_id))
    archive_name = f"{_slugify(topic, 'explainflow-bundle')}-final-bundle.zip"

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as bundle_zip:
        bundle_zip.writestr("script.txt", _transcript_for_scenes(ordered_scenes))

        for index, scene in enumerate(ordered_scenes, start=1):
            scene_stem = _safe_scene_stem(scene, index)

            image_path = _asset_path_from_url(scene.image_url)
            if image_path is not None:
                bundle_zip.write(
                    image_path,
                    arcname=f"images/{scene_stem}{image_path.suffix.lower() or '.png'}",
                )

            audio_path = _asset_path_from_url(scene.audio_url)
            if audio_path is not None:
                bundle_zip.write(
                    audio_path,
                    arcname=f"audio/{scene_stem}{audio_path.suffix.lower() or '.mp3'}",
                )

    return archive_name, buffer.getvalue()
