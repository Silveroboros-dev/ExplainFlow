from __future__ import annotations

import urllib.request
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.schemas.requests import FinalBundleSceneAsset
from app.services.image_pipeline import asset_path_from_url


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


def _transcript_for_scenes(scenes: list[FinalBundleSceneAsset]) -> str:
    chunks: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        title = (scene.title or "").strip() or f"Scene {index}"
        chunks.append(f"Scene {index}: {title}\n\n{scene.text.strip()}")
    return "\n\n---\n\n".join(chunks).strip() + "\n"


def _get_asset_bytes(url: str | None) -> bytes | None:
    if not url:
        return None
    
    # Try local first
    path = asset_path_from_url(url)
    if path and path.exists():
        return path.read_bytes()
    
    # Fallback to downloading (e.g. from GCS)
    if url.startswith("http"):
        try:
            with urllib.request.urlopen(url) as response:
                return response.read()
        except Exception as exc:
            print(f"Failed to download asset from {url}: {exc}")
    
    return None


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

            image_content = _get_asset_bytes(scene.image_url)
            if image_content:
                ext = ".png"
                if scene.image_url and "." in scene.image_url.split("/")[-1]:
                    ext = "." + scene.image_url.split("/")[-1].split(".")[-1]
                bundle_zip.writestr(f"images/{scene_stem}{ext}", image_content)

            audio_content = _get_asset_bytes(scene.audio_url)
            if audio_content:
                ext = ".mp3"
                if scene.audio_url and "." in scene.audio_url.split("/")[-1]:
                    ext = "." + scene.audio_url.split("/")[-1].split(".")[-1]
                bundle_zip.writestr(f"audio/{scene_stem}{ext}", audio_content)

    return archive_name, buffer.getvalue()
