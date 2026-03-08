from io import BytesIO

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.requests import FinalBundleExportRequest, FinalBundleUpscaleRequest
from app.services import build_final_bundle_zip
from app.services.image_pipeline import upscale_image_and_get_url
from app.services.source_ingest import ingest_source_upload

router = APIRouter()


@router.post("/source-assets/upload")
async def upload_source_assets(request: Request, files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="At least one source asset is required.")

    assets = [
        await ingest_source_upload(request=request, upload=upload)
        for upload in files[:8]
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
