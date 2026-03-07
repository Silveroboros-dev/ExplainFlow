from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.requests import FinalBundleExportRequest
from app.services import build_final_bundle_zip

router = APIRouter()


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
