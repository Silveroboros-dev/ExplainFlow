import json
from io import BytesIO
import re

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas.requests import FinalBundleExportRequest, FinalBundleUpscaleRequest
from app.services import build_final_bundle_zip
from app.services.image_pipeline import asset_path_from_reference, upscale_image_and_get_url
from app.services.source_ingest import ingest_source_upload

router = APIRouter()


def _safe_download_filename(filename: str | None, fallback: str) -> str:
    candidate = (filename or "").strip()
    if not candidate:
        return fallback

    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip("-.")
    if not sanitized:
        return fallback
    if not sanitized.lower().endswith(".mp4"):
        sanitized = f"{sanitized}.mp4"
    return sanitized


@router.post("/source-assets/upload")
async def upload_source_assets(
    request: Request,
    files: list[UploadFile] = File(...),
    asset_descriptors: str | None = Form(default=None),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one source asset is required.")

    parsed_descriptors: list[dict] = []
    if isinstance(asset_descriptors, str) and asset_descriptors.strip():
        try:
            candidate = json.loads(asset_descriptors)
            if isinstance(candidate, list):
                parsed_descriptors = [item for item in candidate if isinstance(item, dict)]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid source asset descriptors payload.")

    assets = [
        await ingest_source_upload(
            request=request,
            upload=upload,
            descriptor=parsed_descriptors[idx] if idx < len(parsed_descriptors) else None,
        )
        for idx, upload in enumerate(files[:8])
    ]
    return {
        "status": "success",
        "assets": [asset.model_dump() for asset in assets],
    }


@router.post("/final-bundle/export")
async def export_final_bundle(payload: FinalBundleExportRequest):
    if not payload.scenes:
        raise HTTPException(status_code=400, detail="At least one scene is required to export a final bundle.")

    archive_name, archive_bytes = build_final_bundle_zip(
        topic=payload.topic,
        scenes=payload.scenes,
    )
    return StreamingResponse(
        BytesIO(archive_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{archive_name}"'},
    )


@router.get("/quick-video/download")
async def download_quick_video(video_url: str, filename: str | None = None):
    video_path = asset_path_from_reference(video_url)
    if video_path is None or not video_path.exists() or video_path.suffix.lower() != ".mp4":
        raise HTTPException(status_code=404, detail="Quick MP4 asset not found.")

    download_name = _safe_download_filename(filename, fallback=video_path.name)
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.post("/final-bundle/upscale")
async def upscale_final_bundle(payload: FinalBundleUpscaleRequest, request: Request):
    if not payload.scenes:
        raise HTTPException(status_code=400, detail="At least one scene image is required to upscale a final bundle.")

    updated_scenes: list[dict[str, str | None]] = []
    upscaled_count = 0

    for scene in payload.scenes:
        current_url = scene.image_url
        if not current_url:
            updated_scenes.append(
                {
                    "scene_id": scene.scene_id,
                    "image_url": None,
                    "status": "skipped",
                }
            )
            continue

        try:
            upgraded_url = upscale_image_and_get_url(
                request=request,
                scene_id=scene.scene_id,
                source_url=current_url,
                prefix=f"upscaled_x{payload.scale_factor}",
                scale_factor=payload.scale_factor,
            )
            updated_scenes.append(
                {
                    "scene_id": scene.scene_id,
                    "image_url": upgraded_url,
                    "status": "upscaled",
                }
            )
            upscaled_count += 1
        except FileNotFoundError:
            updated_scenes.append(
                {
                    "scene_id": scene.scene_id,
                    "image_url": current_url,
                    "status": "missing_source",
                }
            )

    if upscaled_count == 0:
        raise HTTPException(status_code=400, detail="Unable to locate source images for the current final bundle.")

    return {
        "status": "success",
        "scale_factor": payload.scale_factor,
        "upscaled_count": upscaled_count,
        "scenes": updated_scenes,
    }
